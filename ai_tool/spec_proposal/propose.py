"""要求 → LLM 仕様候補 → 構造化 → 保存。自動改善はしない。"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.classify import classify_request
from ai_tool.chat_interface.events import event
from ai_tool.chat_interface.llm_errors import classify_llm_error
from ai_tool.policy.evaluate import evaluate_development_work
from ai_tool.spec_proposal.parse import extract_json_object
from ai_tool.spec_proposal.prompt import PROMPT_SYSTEM
from ai_tool.spec_proposal.schema import (
    ORIGIN_LLM_PROPOSAL,
    PHASES_NOT_IMPLEMENTED,
    RAW_CHAR_LIMIT,
    apply_body_fields,
    empty_proposal_body,
    observation_flags,
)
from ai_tool.spec_proposal.store import (
    append_proposal,
    next_version,
    save_last_proposal,
)

ChatFn = Callable[..., Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_id_for(text: str) -> str:
    digest = hashlib.sha256(str(text or "").strip().encode("utf-8")).hexdigest()[:16]
    return f"rq-{digest}"


def new_proposal_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"sp-{stamp}-{uuid.uuid4().hex[:8]}"


def _truncate(text: str, limit: int = RAW_CHAR_LIMIT) -> str:
    blob = str(text or "")
    if len(blob) <= limit:
        return blob
    return blob[:limit] + f"\n… truncated {len(blob) - limit} chars"


def _tool_materials(request: str) -> dict[str, Any]:
    from tools.ai.tool_builder.proposal import PROJECT_CONVENTIONS, create_tool_proposal
    from ai_tool.agent_integration.gpu_process_e2e import registry_index

    registry = list(registry_index().values())
    packed = create_tool_proposal(
        request=request,
        project_spec=PROJECT_CONVENTIONS,
        registry=[
            {
                "name": row.get("name"),
                "category": row.get("category"),
                "description": row.get("description"),
                "module": row.get("module"),
                "function": row.get("function"),
            }
            for row in registry
        ],
        environment={"note": "仕様候補用材料。Registry 変更はしない。"},
    )
    return {
        "used": True,
        "target_request": packed.get("target_request"),
        "rules": packed.get("rules"),
        "registry_count": len(registry),
        "note": "create_tool_proposal の材料。Registry 全文は保存しない。validate_tool_spec は未接続。",
    }


def _policy_items(*, parsed: bool, human_items: list[dict[str, str]], parse_status: str) -> list[dict[str, Any]]:
    product_status = "PARTIAL" if parsed else "NOT_DETERMINED"
    items: list[dict[str, Any]] = [
        {
            "id": "structured_parse",
            "status": "CONNECTED" if parsed else "NOT_IMPLEMENTED",
            "reason": "" if parsed else "LLM output was not SpecificationProposal JSON",
        },
        {
            "id": "claim_status_separated",
            "status": "CONNECTED" if parsed else "NOT_IMPLEMENTED",
            "reason": "CONFIRMED / PROPOSED / ASSUMED / UNKNOWN / HUMAN_CONFIRMATION_REQUIRED",
        },
        {
            "id": "product_specification",
            "status": product_status,
            "provisional": True,
            "provisional_note": (
                "LLM proposal is not a final human specification. "
                "Phase 2 human revision is NOT_IMPLEMENTED."
            ),
        },
        {
            "id": "human_revision",
            "status": "NOT_IMPLEMENTED",
            "reason": "Phase 2",
        },
        {
            "id": "implementation_link",
            "status": "NOT_CONNECTED",
            "reason": "Phase 3",
        },
    ]
    if parse_status == "LLM_ERROR":
        items.append(
            {
                "id": "human_confirmation_required",
                "status": "NEED_HUMAN_DECISION",
                "needs_human": True,
                "reason": "LLM call failed; structured proposal was not observed",
            }
        )
    elif human_items:
        texts = [row["text"] for row in human_items if row.get("text")]
        items.append(
            {
                "id": "human_confirmation_required",
                "status": "NEED_HUMAN_DECISION",
                "needs_human": True,
                "reason": "; ".join(texts)[:500],
            }
        )
    elif not parsed:
        items.append(
            {
                "id": "human_confirmation_required",
                "status": "NEED_HUMAN_DECISION",
                "needs_human": True,
                "reason": "PARSE_FAILED. Free-form text is not a saved specification.",
            }
        )
    else:
        items.append(
            {
                "id": "human_confirmation_required",
                "status": "CONNECTED",
                "reason": "LLM listed no blocking human confirmation",
            }
        )
    return items


def format_proposal_answer(record: dict[str, Any]) -> str:
    def _lines(title: str, rows: list[Any]) -> list[str]:
        if not rows:
            return [f"【{title}】", "（なし）", ""]
        out = [f"【{title}】"]
        for row in rows:
            if isinstance(row, dict):
                out.append(f"- {row.get('text') or ''}")
            else:
                out.append(f"- {row}")
        out.append("")
        return out

    policy = record.get("policy_eval") if isinstance(record.get("policy_eval"), dict) else {}
    decision = policy.get("decision") if isinstance(policy.get("decision"), dict) else {}
    lines = [
        "仕様候補を保存しました。これは最終仕様ではありません。",
        f"proposal_id: {record.get('proposal_id')}",
        f"request_id: {record.get('request_id')}  version: {record.get('version')}",
        f"parse_status: {record.get('parse_status')}",
        f"Policy specification_status: {policy.get('specification_status')}",
        f"may_proceed_implementation: {policy.get('may_proceed_implementation')}",
        f"human_decision_required: {decision.get('human_decision_required')}",
        "",
        "【提案本文】",
        str(record.get("proposed_specification") or "（構造化本文なし）"),
        "",
    ]
    lines.extend(_lines("確定事項 CONFIRMED", record.get("confirmed") or []))
    lines.extend(_lines("LLM提案 PROPOSED", record.get("proposed") or []))
    lines.extend(_lines("仮仕様 ASSUMED", record.get("assumptions") or []))
    lines.extend(_lines("不明点 UNKNOWN", record.get("unknowns") or []))
    lines.extend(_lines("人間確認 HUMAN_CONFIRMATION_REQUIRED", record.get("human_confirmation_required") or []))
    if record.get("parse_status") != "ok" and record.get("llm_raw_truncated"):
        lines.extend(
            [
                "【構造化できなかった LLM 出力（truncated）】",
                str(record.get("llm_raw_truncated")),
                "",
            ]
        )
    if record.get("source") == "chat_tool_creation":
        lines.append("Tool作成要求として扱いました。Registry には登録していません。")
    return "\n".join(lines).strip()


def propose_specification(
    request: str,
    *,
    chat_fn: ChatFn,
    model: str,
    source: str = "api",
    requested_by: str = "user",
    correlation_id: str | None = None,
    session_id: str | None = None,
    development_job_id: str | None = None,
    implementation_id: str | None = None,
    test_run_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    """LLM 仕様候補を構造化して追記保存する。上書きしない。COMPLETE にはしない。"""
    text = str(request or "").strip()
    events: list[dict[str, Any]] = [
        event("spec_proposal", status="started", source=source),
        event("request", text=text, route="spec_proposal"),
    ]
    if not text:
        payload = {
            "ok": False,
            "error": "request が空です",
            "llm_used": False,
            "saved": False,
            "chat_path": "NOT_CONNECTED" if source == "api" else "CONNECTED",
            "agent_py_path": "NOT_CONNECTED",
            "events": events,
        }
        events.append(event("error", where="spec_proposal", message="empty request"))
        return payload

    cid = correlation_id or new_correlation_id()
    if not case_id:
        from ai_tool.chat_interface.execution_case import resolve_case_for_request

        resolved = resolve_case_for_request(originating_request=text, session_id=session_id)
        case_id = resolved.get("case_id")
    rid = request_id_for(text)
    pid = new_proposal_id()
    version = next_version(rid)
    route_hint = classify_request(text)
    use_tool_materials = source == "chat_tool_creation" or route_hint == "tool_creation"
    tool_materials = _tool_materials(text) if use_tool_materials else {"used": False}
    if use_tool_materials:
        events.append(
            event(
                "tool_create",
                status="設計中",
                registry_write=False,
                step="proposal_materials",
                reused="create_tool_proposal",
            )
        )

    user_payload: dict[str, Any] = {"request": text, "source": source}
    if tool_materials.get("used"):
        user_payload["tool_proposal_materials"] = {
            "target_request": tool_materials.get("target_request"),
            "rules": tool_materials.get("rules"),
        }

    raw = ""
    llm_error = None
    classified = None
    try:
        response = chat_fn(
            model=model,
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        raw = str(getattr(getattr(response, "message", None), "content", None) or "")
        events.append(event("llm_input", kind="specification_proposal", material_count=1))
        events.append(event("llm_output", kind="specification_proposal"))
        events.append(event("llm", model=model, kind="specification_proposal"))
    except Exception as exc:  # noqa: BLE001
        llm_error = f"{type(exc).__name__}: {exc}"
        classified = classify_llm_error(llm_error)
        events.append(
            event(
                "error",
                where="spec_proposal_llm",
                kind=classified["kind"],
                message=llm_error,
                user_message=classified["user_message"],
            )
        )

    parsed_obj = extract_json_object(raw) if not llm_error else None
    parse_status = "ok"
    if llm_error:
        parse_status = "LLM_ERROR"
    elif parsed_obj is None:
        parse_status = "PARSE_FAILED"

    body = empty_proposal_body()
    if parsed_obj is not None:
        apply_body_fields(body, parsed_obj)
    elif parse_status == "PARSE_FAILED":
        body["unknowns"] = [
            {
                "text": "LLM output was not SpecificationProposal JSON",
                "status": "UNKNOWN",
            }
        ]

    human_items = list(body.get("human_confirmation_required") or [])
    policy_eval = evaluate_development_work(
        items=_policy_items(parsed=parsed_obj is not None, human_items=human_items, parse_status=parse_status),
        tests_passed=None,
        claim_specification_complete=False,
        save=False,
    )

    record: dict[str, Any] = {
        "ok": llm_error is None,
        "proposal_id": pid,
        "request_id": rid,
        "version": version,
        "created_at": _now(),
        "correlation_id": cid,
        "requested_by": requested_by,
        "source": source,
        "origin": ORIGIN_LLM_PROPOSAL,
        "parent_proposal_id": None,
        "phase": 1,
        "request": text,
        "model": model,
        "llm_used": True,
        "parse_status": parse_status,
        "confidence": "UNCONFIRMED",
        "provisional": True,
        "overwrite": False,
        "supersedes": None,
        "human_revision": None,
        "final_specification": None,
        "revision_reason": None,
        "difference_vs_human": None,
        "llm_judgment": "NOT_IMPLEMENTED",
        "session_id": session_id,
        "development_job_id": development_job_id,
        "implementation_id": implementation_id,
        "test_run_id": test_run_id,
        "case_id": case_id,
        "cursor_record": "NOT_OBSERVED",
        "phases_not_implemented": list(PHASES_NOT_IMPLEMENTED),
        "tool_materials": tool_materials,
        "validate_tool_spec": "NOT_CONNECTED",
        "agent_py_path": "NOT_CONNECTED",
        "chat_path": "CONNECTED" if source.startswith("chat_") else "NOT_CONNECTED",
        "entrypoint_assumption": (
            "Chat route=chat and research are NOT_CONNECTED. "
            "agent.py is NOT_CONNECTED. "
            "tool_creation and development Chat routes plus POST /api/spec/propose are connected."
        ),
        "llm_raw_truncated": _truncate(raw) if raw else "",
        "policy_eval": {
            "specification_status": policy_eval.get("specification_status"),
            "test_status": policy_eval.get("test_status"),
            "may_claim_specification_complete": policy_eval.get("may_claim_specification_complete"),
            "may_proceed_implementation": policy_eval.get("may_proceed_implementation"),
            "blocked_complete_claim": policy_eval.get("blocked_complete_claim"),
            "tests_passed_implies_specification_complete": False,
            "decision": policy_eval.get("decision"),
            "items": policy_eval.get("items"),
        },
        "events": events,
    }
    record.update(observation_flags())
    record.update(body)
    if llm_error:
        record["error"] = llm_error
        record["error_kind"] = (classified or {}).get("kind")
        record["user_error"] = (classified or {}).get("user_message")
        record["is_error"] = True
    else:
        record["is_error"] = False

    events.append(
        event(
            "spec_proposal",
            status="saved",
            proposal_id=pid,
            request_id=rid,
            version=version,
            parse_status=parse_status,
            overwrite=False,
        )
    )
    if source == "chat_tool_creation":
        events.append(
            event(
                "tool_create",
                status="ユーザー確認待ち",
                registry_write=False,
                register_tool_called=False,
            )
        )

    record["saved"] = True
    record["answer"] = format_proposal_answer(record)
    if case_id:
        for ev in events:
            if isinstance(ev, dict):
                ev.setdefault("case_id", case_id)
    append_proposal(record)
    save_last_proposal(record)
    if case_id:
        from ai_tool.chat_interface.execution_case import link_member

        link_member(str(case_id), "proposal_id", str(pid))
        link_member(str(case_id), "correlation_id", str(cid))
    return record
