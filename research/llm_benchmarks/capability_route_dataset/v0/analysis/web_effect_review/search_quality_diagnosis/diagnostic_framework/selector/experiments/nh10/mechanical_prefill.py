"""NH10 mechanical prefill from materials. Does not invent causes."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

NH10 = Path(__file__).resolve().parent
NH9 = NH10.parent / "nh9"
NH8 = NH10.parent / "nh8"
sys.path.insert(0, str(NH9))
sys.path.insert(0, str(NH8))

from fixed_slots import empty_slot, status  # noqa: E402
from uncertainty_gate import material_hints  # noqa: E402


def apply_mechanical_prefill(
    slots: dict[str, dict[str, Any]],
    materials: dict[str, Any],
) -> dict[str, Any]:
    """Return updated slots + applied rules. Never fabricates evidence IDs."""
    out = {k: dict(v) for k, v in (slots or {}).items()}
    applied: list[dict[str, Any]] = []
    hints = material_hints(materials)
    runtime = str((materials or {}).get("runtime_log") or "")
    code = str((materials or {}).get("code_excerpt") or "")
    state = str((materials or {}).get("state_context") or "")
    evid = str((materials or {}).get("evidence") or "")
    summary = str((materials or {}).get("problem_summary") or "")
    blob = json.dumps(materials or {}, ensure_ascii=False).lower()

    def maybe_set(name: str, payload: dict[str, Any], rule_id: str, evid_key: str, allowed: list[str]) -> None:
        if status(out, name) not in allowed:
            return
        cur = out.get(name) or empty_slot()
        st = payload["status"]
        val = payload.get("value")
        out[name] = {
            "status": st,
            "value": val if st != "UNKNOWN" else None,
            "confidence": "high",
            "evidence_reference": f"prefill:{evid_key}",
            "prefill_rule": rule_id,
        }
        applied.append({"rule": rule_id, "slot": name, "from": cur.get("status"), "to": st, "evidence": evid_key})

    if "[observed]" in runtime.lower():
        maybe_set("stdout_present", {"status": "OBSERVED", "value": True}, "runtime_observed_line", "runtime_log", ["UNKNOWN", "NOT_OBSERVED"])
        maybe_set(
            "runtime_issue_observed",
            {"status": "OBSERVED", "value": True},
            "runtime_observed_line",
            "runtime_log",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("runtime_none"):
        maybe_set("stdout_present", {"status": "NOT_OBSERVED", "value": False}, "runtime_none", "runtime_log", ["UNKNOWN", "OBSERVED"])
        maybe_set(
            "runtime_issue_observed",
            {"status": "NOT_OBSERVED", "value": False},
            "runtime_none",
            "runtime_log",
            ["UNKNOWN", "OBSERVED"],
        )
    if code.strip() and not code.strip().startswith("なし"):
        maybe_set(
            "code_scope_present",
            {"status": "OBSERVED", "value": True},
            "code_excerpt_present",
            "code_excerpt",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
        if ("3ファイル" in code or "2ファイル" in code or code.count(".py") >= 2 or "跨ぎ" in code):
            maybe_set(
                "code_multi_file",
                {"status": "OBSERVED", "value": True},
                "code_multi_file_hint",
                "code_excerpt",
                ["UNKNOWN", "NOT_OBSERVED"],
            )
    elif code.strip().startswith("なし"):
        maybe_set(
            "code_scope_present",
            {"status": "NOT_OBSERVED", "value": False},
            "code_excerpt_none",
            "code_excerpt",
            ["UNKNOWN", "OBSERVED"],
        )
    if any(k in state for k in ["変更なし", "変更要求はない", "State 変更なし", "State/Evidence 変更なし"]):
        for name in ("state_change_requested", "goal_change_requested", "reopen_requested"):
            maybe_set(name, {"status": "NOT_OBSERVED", "value": False}, "state_no_change", "state_context", ["UNKNOWN"])
    if hints.get("mentions_reopen"):
        maybe_set("reopen_requested", {"status": "OBSERVED", "value": True}, "reopen_mentioned", "state_context", ["UNKNOWN", "NOT_OBSERVED"])
        maybe_set(
            "state_change_requested",
            {"status": "OBSERVED", "value": True},
            "reopen_mentioned",
            "state_context",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_evidence_id"):
        maybe_set("evidence_present", {"status": "OBSERVED", "value": True}, "evidence_id_present", "evidence", ["UNKNOWN", "NOT_OBSERVED"])
    if "exists=true" in evid.lower() or "exists=true" in blob:
        maybe_set(
            "evidence_exists_known",
            {"status": "OBSERVED", "value": True},
            "evidence_exists_true",
            "evidence",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_content_mismatch"):
        maybe_set(
            "evidence_content_mismatch",
            {"status": "OBSERVED", "value": True},
            "content_mismatch",
            "evidence",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
        maybe_set(
            "evidence_content_known",
            {"status": "OBSERVED", "value": False},
            "content_mismatch",
            "evidence",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_disagreement"):
        maybe_set(
            "llm_disagreement",
            {"status": "OBSERVED", "value": True},
            "llm_disagreement",
            "prior_analysis",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_small_unverified"):
        maybe_set(
            "small_llm_unverified",
            {"status": "OBSERVED", "value": True},
            "small_unverified",
            "prior_analysis",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_near_exact"):
        maybe_set(
            "near_exact_surface",
            {"status": "OBSERVED", "value": True},
            "near_exact",
            "state_history",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_similar_new"):
        maybe_set(
            "similar_new_meaning",
            {"status": "OBSERVED", "value": True},
            "similar_new",
            "state_history",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
    if hints.get("mentions_state_update") and not hints.get("mentions_reopen"):
        maybe_set(
            "state_change_requested",
            {"status": "OBSERVED", "value": True},
            "state_update_hint",
            "problem_summary",
            ["UNKNOWN", "NOT_OBSERVED"],
        )
        if "goal" in (summary + state).lower() or "Goal" in summary + state:
            maybe_set(
                "goal_change_requested",
                {"status": "OBSERVED", "value": True},
                "state_update_hint",
                "problem_summary",
                ["UNKNOWN", "NOT_OBSERVED"],
            )

    return {"slots": out, "applied": applied, "hints": hints}
