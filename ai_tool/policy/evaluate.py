"""仕様項目の状態と完成判定。LLM の自己申告を上書きする。"""
from __future__ import annotations

import json
from typing import Any

from ai_tool.policy.loader import PolicyLoadError, load_development_policy
from ai_tool.policy.paths import last_eval_path

ITEM_STATUSES = (
    "CONNECTED",
    "PARTIAL",
    "NOT_IMPLEMENTED",
    "NOT_CONNECTED",
    "NOT_OBSERVED",
    "NOT_DETERMINED",
    "NEED_HUMAN_DECISION",
)

INCOMPLETE_STATUSES = frozenset({"NOT_IMPLEMENTED", "NOT_CONNECTED"})
PARTIAL_STATUSES = frozenset({"PARTIAL", "NOT_OBSERVED", "NOT_DETERMINED"})


def _norm_status(raw: Any) -> str:
    text = str(raw or "").strip().upper().replace(" ", "_")
    if text in ITEM_STATUSES:
        return text
    return "NOT_DETERMINED"


def _item(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {
            "id": "unknown",
            "status": "NOT_DETERMINED",
            "provisional": False,
            "provisional_note": "",
            "needs_human": False,
            "reason": "item が object ではない",
        }
    note = str(row.get("provisional_note") or "").strip()
    provisional = bool(row.get("provisional"))
    return {
        "id": str(row.get("id") or "").strip() or "unnamed",
        "status": _norm_status(row.get("status")),
        "provisional": provisional,
        "provisional_note": note,
        "needs_human": bool(row.get("needs_human")) or _norm_status(row.get("status")) == "NEED_HUMAN_DECISION",
        "reason": str(row.get("reason") or "").strip(),
        "evidence": str(row.get("evidence") or "").strip(),
    }


def unfinished_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        if item["status"] != "CONNECTED" or item["provisional"] or item["needs_human"]:
            out.append(
                {
                    "id": item["id"],
                    "status": item["status"],
                    "provisional": item["provisional"],
                    "needs_human": item["needs_human"],
                    "reason": item["reason"] or "未完成",
                }
            )
    return out


def evaluate_development_work(
    *,
    items: list[Any] | None = None,
    tests_passed: bool | None = None,
    claim_specification_complete: bool = False,
    save: bool = True,
    policy_path=None,
) -> dict[str, Any]:
    """仕様完成とテスト成功を分離する。空のチェックリストでは COMPLETE にしない。"""
    load_error = None
    policy: dict[str, Any] | None = None
    try:
        policy = load_development_policy(path=policy_path)
    except PolicyLoadError as exc:
        load_error = str(exc)

    normalized = [_item(row) for row in (items or [])]
    human = any(row["needs_human"] for row in normalized)
    provisional_without_note = [
        row["id"] for row in normalized if row["provisional"] and not row["provisional_note"]
    ]
    if provisional_without_note:
        human = True

    if tests_passed is True:
        test_status = "PASS"
    elif tests_passed is False:
        test_status = "FAIL"
    else:
        test_status = "NOT_OBSERVED"

    if load_error:
        spec = "NOT_OBSERVED"
        decision = "INCOMPLETE"
        confidence = "UNCONFIRMED"
    elif not normalized:
        spec = "NOT_OBSERVED"
        decision = "INCOMPLETE"
        confidence = "UNCONFIRMED"
    elif human:
        spec = "NEED_HUMAN_DECISION"
        decision = "INCOMPLETE"
        confidence = "UNCONFIRMED"
    elif any(row["status"] in INCOMPLETE_STATUSES for row in normalized):
        spec = "INCOMPLETE"
        decision = "INCOMPLETE"
        confidence = "UNCONFIRMED"
    elif any(row["status"] in PARTIAL_STATUSES or row["provisional"] for row in normalized):
        spec = "PARTIAL"
        decision = "PARTIAL"
        confidence = "UNCONFIRMED"
    elif all(row["status"] == "CONNECTED" for row in normalized):
        spec = "COMPLETE"
        decision = "COMPLETE"
        confidence = "CONFIRMED"
    else:
        spec = "PARTIAL"
        decision = "PARTIAL"
        confidence = "UNCONFIRMED"

    if spec == "COMPLETE" and test_status == "PASS":
        pass
    if spec == "COMPLETE" and not normalized:
        spec = "NOT_OBSERVED"
        decision = "INCOMPLETE"
        confidence = "UNCONFIRMED"

    blocked = bool(claim_specification_complete and spec != "COMPLETE")
    payload = {
        "ok": load_error is None,
        "policy_id": (policy or {}).get("policy_id") if policy else None,
        "policy_version": (policy or {}).get("version") if policy else None,
        "policy_loaded": load_error is None,
        "policy_load_error": load_error,
        "decision": {
            "status": decision,
            "confidence": confidence,
            "missing": unfinished_items(normalized),
            "human_decision_required": human or spec == "NEED_HUMAN_DECISION",
            "reason": _reasons(normalized, load_error, human, provisional_without_note, blocked, spec, test_status),
        },
        "specification_status": spec,
        "test_status": test_status,
        "tests_passed_implies_specification_complete": False,
        "blocked_complete_claim": blocked,
        "may_claim_specification_complete": spec == "COMPLETE",
        "may_proceed_implementation": load_error is None and not human,
        "items": normalized,
        "enforced": True,
        "llm_used": False,
        "chat_path": "NOT_CONNECTED",
        "research": "NOT_CONNECTED",
    }
    if save:
        target = last_eval_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def _reasons(
    items: list[dict[str, Any]],
    load_error: str | None,
    human: bool,
    provisional_without_note: list[str],
    blocked: bool,
    spec: str,
    test_status: str,
) -> list[str]:
    reasons: list[str] = []
    if load_error:
        reasons.append("policy_load_failed")
    if not items:
        reasons.append("empty_checklist_cannot_complete")
    if human:
        reasons.append("human_decision_required")
    if provisional_without_note:
        reasons.append("provisional_without_note:" + ",".join(provisional_without_note))
    if blocked:
        reasons.append("complete_claim_blocked")
    if spec != "COMPLETE" and test_status == "PASS":
        reasons.append("test_pass_is_not_specification_complete")
    for row in items:
        if row["status"] != "CONNECTED" or row["provisional"] or row["needs_human"]:
            reasons.append(f"{row['id']}={row['status']}")
    return reasons
