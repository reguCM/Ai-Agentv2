"""Map NH12-2 compression slots to NH9 observation slots (mechanical, no LLM)."""

from __future__ import annotations

from typing import Any

from mechanical_compression import COMPRESSION_SLOTS, empty_unknown

import sys
from pathlib import Path

NH9 = Path(__file__).resolve().parent.parent / "nh9"
sys.path.insert(0, str(NH9))
from fixed_slots import SLOTS, empty_slot  # noqa: E402


def _st(compressed: dict[str, Any], name: str) -> str:
    s = (compressed.get("compression_slots") or {}).get(name) or empty_unknown()
    st = s.get("status")
    if st in {"FACT", "PRESENT"}:
        val = s.get("value")
        if val is False:
            return "NOT_OBSERVED"
        return "OBSERVED"
    if st == "ABSENT":
        return "NOT_OBSERVED"
    return "UNKNOWN"


def _val(compressed: dict[str, Any], name: str) -> Any:
    s = (compressed.get("compression_slots") or {}).get(name) or empty_unknown()
    st = s.get("status")
    if st in {"FACT", "PRESENT"}:
        v = s.get("value")
        if isinstance(v, bool):
            return v
        return True if v else None
    if st == "ABSENT":
        return False
    return None


def map_compression_to_observation_slots(compressed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Condition B: mechanical mapping only."""
    c = compressed
    mapping_rules: list[str] = []

    def obs(name: str, from_comp: str | None = None) -> dict[str, Any]:
        comp = from_comp or name
        st = _st(c, comp)
        val = _val(c, comp)
        mapping_rules.append(f"{comp}->{name}:{st}")
        return {
            "status": st,
            "value": val if st != "UNKNOWN" else None,
            "confidence": "high" if st != "UNKNOWN" else "low",
            "evidence_reference": f"compression:{comp}",
            "mapping": "mechanical_b",
        }

    out: dict[str, dict[str, Any]] = {}
    tool_st = _st(c, "tool")
    out["entry_detected"] = {
        "status": "OBSERVED" if tool_st == "OBSERVED" else ("NOT_OBSERVED" if tool_st == "NOT_OBSERVED" else "UNKNOWN"),
        "value": tool_st == "OBSERVED",
        "confidence": "high",
        "evidence_reference": "compression:tool",
        "mapping": "mechanical_b",
    }
    out["backend_identified"] = obs("backend_identified", "search")
    out["collect_filter_present"] = obs("collect_filter_present", "ranking")
    out["ranking_present"] = obs("ranking_present", "ranking")
    out["ranking_filter_separated"] = obs("ranking_filter_separated", "ranking")
    out["stdout_present"] = obs("stdout_present", "runtime")
    out["llm_handoff_present"] = obs("llm_handoff_present", "output")
    out["json_serialization_present"] = obs("json_serialization_present", "output")
    out["state_change_requested"] = obs("state_change_requested", "state")
    out["goal_change_requested"] = empty_slot("UNKNOWN")
    out["claim_change_requested"] = empty_slot("UNKNOWN")
    out["hypothesis_change_requested"] = empty_slot("UNKNOWN")
    out["reopen_requested"] = empty_slot("UNKNOWN")
    out["evidence_present"] = obs("evidence_present", "evidence")
    out["evidence_exists_known"] = obs("evidence_exists_known", "evidence")
    out["evidence_content_known"] = obs("evidence_content_known", "evidence")
    out["evidence_freshness_known"] = obs("evidence_freshness_known", "timestamp")
    err_st = _st(c, "error")
    out["runtime_issue_observed"] = {
        "status": "OBSERVED" if err_st == "OBSERVED" else ("NOT_OBSERVED" if err_st == "NOT_OBSERVED" else "UNKNOWN"),
        "value": err_st == "OBSERVED",
        "confidence": "high" if err_st != "UNKNOWN" else "low",
        "evidence_reference": "compression:error",
        "mapping": "mechanical_b",
    }
    out["test_failure_observed"] = empty_slot("UNKNOWN")
    out["code_scope_present"] = obs("code_scope_present", "code_path")
    out["caller_scope_present"] = empty_slot("UNKNOWN")
    out["llm_disagreement"] = empty_slot("UNKNOWN")
    out["code_multi_file"] = empty_slot("UNKNOWN")
    out["small_llm_unverified"] = empty_slot("UNKNOWN")
    out["near_exact_surface"] = empty_slot("UNKNOWN")
    out["similar_new_meaning"] = empty_slot("UNKNOWN")
    out["off_path_cause_mentioned"] = empty_slot("UNKNOWN")
    out["evidence_content_mismatch"] = empty_slot("UNKNOWN")

    for name in SLOTS:
        if name not in out:
            out[name] = empty_slot("UNKNOWN")

    return {"slots": out, "mapping_rules": mapping_rules, "condition": "B"}
