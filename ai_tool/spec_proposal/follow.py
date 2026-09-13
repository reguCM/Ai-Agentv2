"""人間修正・問題発覚の追記。LLM 提案は上書きしない。正しさは自動判定しない。"""
from __future__ import annotations

from typing import Any

from ai_tool.chat_interface.activity import new_correlation_id
from ai_tool.chat_interface.events import event
from ai_tool.spec_proposal.propose import new_proposal_id, request_id_for
from ai_tool.spec_proposal.schema import (
    ORIGIN_HUMAN_REVISION,
    ORIGIN_PROBLEM_RECORD,
    PHASES_NOT_IMPLEMENTED,
    apply_body_fields,
    empty_proposal_body,
    observation_flags,
)
from ai_tool.spec_proposal.store import (
    append_proposal,
    get_by_proposal_id,
    next_version,
    save_last_proposal,
)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _commit(record: dict[str, Any]) -> dict[str, Any]:
    record["saved"] = True
    cid = str(record.get("case_id") or "").strip()
    if cid:
        for ev in record.get("events") or []:
            if isinstance(ev, dict):
                ev.setdefault("case_id", cid)
    append_proposal(record)
    save_last_proposal(record)
    if cid:
        from ai_tool.chat_interface.execution_case import link_member

        pid = str(record.get("proposal_id") or "")
        if pid:
            link_member(cid, "proposal_id", pid)
        corr = str(record.get("correlation_id") or "")
        if corr:
            link_member(cid, "correlation_id", corr)
    return record


def _parent_or_error(parent_proposal_id: str) -> dict[str, Any]:
    want = _text(parent_proposal_id)
    if not want:
        return {
            "ok": False,
            "saved": False,
            "error": "parent_proposal_id が空です",
            "llm_used": False,
            "llm_judgment": "NOT_IMPLEMENTED",
        }
    parent = get_by_proposal_id(want)
    if not parent:
        return {
            "ok": False,
            "saved": False,
            "error": "parent_proposal_id が見つからない",
            "parent_proposal_id": want,
            "llm_used": False,
            "llm_judgment": "NOT_IMPLEMENTED",
        }
    return {"ok": True, "parent": parent}


def append_human_revision(
    *,
    parent_proposal_id: str,
    revision_reason: str = "",
    request: str | None = None,
    body: dict[str, Any] | None = None,
    requested_by: str = "user",
    session_id: str | None = None,
    development_job_id: str | None = None,
    implementation_id: str | None = None,
    test_run_id: str | None = None,
    case_id: str | None = None,
    source: str = "api",
) -> dict[str, Any]:
    """人間修正を別レコードで追記する。親 LLM 案は書き換えない。LLM は呼ばない。"""
    found = _parent_or_error(parent_proposal_id)
    if not found.get("ok"):
        return found
    parent = found["parent"]
    request_id = str(parent.get("request_id") or "") or request_id_for(_text(request) or str(parent.get("request") or ""))
    pid = new_proposal_id()
    version = next_version(request_id)
    reason = _text(revision_reason)
    spec_body = empty_proposal_body()
    if isinstance(body, dict):
        apply_body_fields(spec_body, body)
    events = [
        event("spec_revision", status="started", parent_proposal_id=parent.get("proposal_id")),
        event(
            "spec_revision",
            status="saved",
            proposal_id=pid,
            parent_proposal_id=parent.get("proposal_id"),
            overwrite=False,
        ),
    ]
    record: dict[str, Any] = {
        "ok": True,
        "proposal_id": pid,
        "request_id": request_id,
        "version": version,
        "created_at": _now(),
        "correlation_id": new_correlation_id(),
        "requested_by": requested_by,
        "source": source,
        "origin": ORIGIN_HUMAN_REVISION,
        "parent_proposal_id": parent.get("proposal_id"),
        "request": _text(request) if request is not None else str(parent.get("request") or ""),
        "model": None,
        "llm_used": False,
        "parse_status": "human_authored",
        "confidence": "UNCONFIRMED",
        "provisional": True,
        "overwrite": False,
        "revision_reason": reason,
        "revision_reason_status": "UNKNOWN" if not reason else "PROVIDED",
        "llm_judgment": "NOT_IMPLEMENTED",
        "session_id": session_id or parent.get("session_id"),
        "development_job_id": development_job_id or parent.get("development_job_id"),
        "implementation_id": implementation_id or parent.get("implementation_id"),
        "test_run_id": test_run_id or parent.get("test_run_id"),
        "case_id": case_id or parent.get("case_id"),
        "cursor_record": "NOT_OBSERVED",
        "phases_not_implemented": list(PHASES_NOT_IMPLEMENTED),
        "chat_path": "NOT_CONNECTED",
        "agent_py_path": "NOT_CONNECTED",
        "events": events,
        "is_error": False,
    }
    record.update(observation_flags())
    record.update(spec_body)
    record["answer"] = (
        "人間修正を追記しました。元の LLM 提案は上書きしていません。"
        f" parent={parent.get('proposal_id')} new={pid}"
        " llm_judgment=NOT_IMPLEMENTED"
    )
    return _commit(record)


def append_problem_record(
    *,
    parent_proposal_id: str,
    problem: str,
    cause: str = "",
    cause_status: str = "NOT_DETERMINED",
    human_correction: str = "",
    revision_reason: str = "",
    impact: str = "",
    recurrence_prevention: str = "",
    requested_by: str = "user",
    session_id: str | None = None,
    development_job_id: str | None = None,
    implementation_id: str | None = None,
    test_run_id: str | None = None,
    case_id: str | None = None,
    source: str = "api",
) -> dict[str, Any]:
    """問題発覚を別レコードで追記する。原因が無いときは NOT_DETERMINED。LLM 成否は付けない。"""
    found = _parent_or_error(parent_proposal_id)
    if not found.get("ok"):
        return found
    parent = found["parent"]
    text = _text(problem)
    if not text:
        return {
            "ok": False,
            "saved": False,
            "error": "problem が空です",
            "llm_used": False,
            "llm_judgment": "NOT_IMPLEMENTED",
        }
    cause_st = _text(cause_status).upper().replace(" ", "_") or "NOT_DETERMINED"
    allowed_cause = {
        "NOT_DETERMINED",
        "NOT_OBSERVED",
        "UNKNOWN",
        "PROVIDED",
        "ASSUMED",
    }
    if cause_st not in allowed_cause:
        cause_st = "NOT_DETERMINED"
    if _text(cause) and cause_st == "NOT_DETERMINED":
        cause_st = "PROVIDED"
    if not _text(cause):
        cause_st = "NOT_DETERMINED"
    request_id = str(parent.get("request_id") or "")
    pid = new_proposal_id()
    version = next_version(request_id)
    events = [
        event("spec_problem", status="started", parent_proposal_id=parent.get("proposal_id")),
        event(
            "spec_problem",
            status="saved",
            proposal_id=pid,
            parent_proposal_id=parent.get("proposal_id"),
            overwrite=False,
        ),
    ]
    record: dict[str, Any] = {
        "ok": True,
        "proposal_id": pid,
        "request_id": request_id,
        "version": version,
        "created_at": _now(),
        "correlation_id": new_correlation_id(),
        "requested_by": requested_by,
        "source": source,
        "origin": ORIGIN_PROBLEM_RECORD,
        "parent_proposal_id": parent.get("proposal_id"),
        "request": str(parent.get("request") or ""),
        "model": None,
        "llm_used": False,
        "parse_status": "problem_record",
        "confidence": "UNCONFIRMED",
        "provisional": True,
        "overwrite": False,
        "problem": text,
        "cause": _text(cause),
        "cause_status": cause_st,
        "human_correction": _text(human_correction),
        "revision_reason": _text(revision_reason),
        "impact": _text(impact),
        "recurrence_prevention": _text(recurrence_prevention),
        "llm_judgment": "NOT_IMPLEMENTED",
        "session_id": session_id or parent.get("session_id"),
        "development_job_id": development_job_id or parent.get("development_job_id"),
        "implementation_id": implementation_id or parent.get("implementation_id"),
        "test_run_id": test_run_id or parent.get("test_run_id"),
        "case_id": case_id or parent.get("case_id"),
        "cursor_record": "NOT_OBSERVED",
        "phases_not_implemented": list(PHASES_NOT_IMPLEMENTED),
        "chat_path": "NOT_CONNECTED",
        "agent_py_path": "NOT_CONNECTED",
        "events": events,
        "is_error": False,
    }
    record.update(observation_flags())
    record.update(empty_proposal_body())
    record["answer"] = (
        "問題記録を追記しました。元の提案は上書きしていません。"
        f" parent={parent.get('proposal_id')} new={pid}"
        f" cause_status={cause_st} llm_judgment=NOT_IMPLEMENTED"
    )
    return _commit(record)
