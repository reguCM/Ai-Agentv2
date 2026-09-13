"""NH10 high_slots gate with reason→slot→evidence mapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

NH10 = Path(__file__).resolve().parent
NH9 = NH10.parent / "nh9"
NH8 = NH10.parent / "nh8"
sys.path.insert(0, str(NH9))
sys.path.insert(0, str(NH8))

from fixed_slots import map_slots_to_features, observed_true, status  # noqa: E402
from uncertainty_gate import evaluate_uncertainty, material_hints  # noqa: E402

REASON_MAP = json.loads((NH10 / "reason_to_slot_map.json").read_text(encoding="utf-8"))


def _code_present(materials: dict[str, Any]) -> bool:
    code = str((materials or {}).get("code_excerpt") or "").strip()
    if not code:
        return False
    # "なし（…）" is absence, not a real excerpt
    if code.startswith("なし") or code.lower() in {"none", "n/a", "na"}:
        return False
    return True


def _evidence_for(slot: str, materials: dict[str, Any]) -> list[str]:
    keys = REASON_MAP.get("evidence_keys", {}).get(slot) or []
    out = []
    for k in keys:
        if (materials or {}).get(k):
            out.append(k)
    return out or ["materials"]


def _item(slot: str, reason: str, materials: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "slot": slot,
        "reason": reason,
        "evidence": _evidence_for(slot, materials),
        "source": source,
    }


def build_high_slots(
    *,
    slots: dict[str, dict[str, Any]],
    materials: dict[str, Any],
    mapped: dict[str, Any] | None = None,
    parse_ok: bool = True,
    empty_output: bool = False,
    prefill_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mechanical gate. LLM does not choose escalation."""
    mapped = mapped or map_slots_to_features(slots, materials)
    features = dict(mapped.get("features") or {})
    hints = material_hints(materials)
    items: list[dict[str, Any]] = []
    reasons: list[str] = []

    base = evaluate_uncertainty(
        materials=materials,
        observation={"inferences_not_facts": [], "prior_analysis_notes": [], "hallucinated_feature_keys": []},
        mapped=mapped,
        parse_ok=parse_ok,
        empty_output=empty_output,
    )
    reasons.extend(base.get("reasons") or [])

    # Map every NH8 reason to explicit high slots
    rmap = REASON_MAP.get("reason_to_slots") or {}
    for r in list(reasons):
        for slot in rmap.get(r) or []:
            items.append(_item(slot, r, materials, "nh8_reason"))

    # Slot-hint gaps (same spirit as NH9 high_slots, but structured)
    if hints["mentions_state_update"] and not observed_true(slots, "state_change_requested") and not observed_true(
        slots, "goal_change_requested"
    ):
        items.append(_item("state_change_requested", "state_hint_slot_gap", materials, "slot_hint"))
        reasons.append("state_hint_slot_gap")
    if hints["mentions_reopen"] and not observed_true(slots, "reopen_requested"):
        items.append(_item("reopen_requested", "reopen_hint_slot_gap", materials, "slot_hint"))
        reasons.append("reopen_hint_slot_gap")
    if hints["mentions_evidence_id"] and not observed_true(slots, "evidence_present"):
        items.append(_item("evidence_present", "evidence_hint_slot_gap", materials, "slot_hint"))
        reasons.append("evidence_hint_slot_gap")
    if hints["mentions_content_mismatch"] and not observed_true(slots, "evidence_content_mismatch"):
        items.append(_item("evidence_content_mismatch", "content_mismatch_slot_gap", materials, "slot_hint"))
        reasons.append("content_mismatch_slot_gap")
    if hints["mentions_disagreement"] and not observed_true(slots, "llm_disagreement"):
        items.append(_item("llm_disagreement", "disagreement_slot_gap", materials, "slot_hint"))
        reasons.append("disagreement_slot_gap")
    if hints["mentions_small_unverified"] and not observed_true(slots, "small_llm_unverified"):
        items.append(_item("small_llm_unverified", "small_unverified_slot_gap", materials, "slot_hint"))
        reasons.append("small_unverified_slot_gap")
    if observed_true(slots, "reopen_requested") and status(slots, "evidence_exists_known") != "OBSERVED":
        items.append(_item("evidence_exists_known", "reopen_without_evidence_exists", materials, "slot_hint"))
        reasons.append("reopen_without_evidence_exists")
    if observed_true(slots, "evidence_present") and status(slots, "evidence_content_known") == "UNKNOWN":
        items.append(_item("evidence_content_known", "evidence_content_unknown", materials, "slot_hint"))
        reasons.append("evidence_content_unknown")

    # Sparse / H-type: real code excerpt + no runtime → always confirm (NH9 miss)
    code_present = _code_present(materials)
    runtime_none = bool(hints.get("runtime_none"))
    feat_true = sum(1 for v in features.values() if v is True)
    if code_present and runtime_none:
        reasons.append("sparse_fingerprint_insufficient_info")
        for slot in rmap.get("sparse_fingerprint_insufficient_info") or [
            "code_scope_present",
            "runtime_issue_observed",
            "caller_scope_present",
        ]:
            items.append(_item(slot, "sparse_fingerprint_insufficient_info", materials, "sparse_fingerprint"))
    elif code_present and features.get("code_available") is not True:
        reasons.append("code_excerpt_missed")
        items.append(_item("code_scope_present", "code_excerpt_missed", materials, "prefill"))
    elif feat_true == 0 and code_present:
        reasons.append("sparse_fingerprint_insufficient_info")
        items.append(_item("code_scope_present", "sparse_fingerprint_insufficient_info", materials, "sparse_fingerprint"))
    # Drop false NH8 reason when code_excerpt is literally なし
    if not code_present and "insufficient_runtime_with_code_only" in reasons:
        reasons = [r for r in reasons if r != "insufficient_runtime_with_code_only"]
        items = [it for it in items if it.get("reason") != "insufficient_runtime_with_code_only"]

    # Deduplicate by slot (keep first reason)
    seen: set[str] = set()
    uniq_items: list[dict[str, Any]] = []
    for it in items:
        if it["slot"] in seen:
            continue
        seen.add(it["slot"])
        uniq_items.append(it)

    uniq_reasons: list[str] = []
    rseen: set[str] = set()
    for r in reasons:
        if r not in rseen:
            rseen.add(r)
            uniq_reasons.append(r)

    level = "HIGH" if uniq_items or uniq_reasons else "LOW"
    # Prefer HUMAN_REVIEW when sparse insufficient info remains after mapping
    escalation = "NONE"
    if level == "HIGH":
        if "sparse_fingerprint_insufficient_info" in uniq_reasons:
            escalation = "HUMAN_REVIEW"
        else:
            escalation = "LARGE_LLM"

    return {
        "level": level,
        "high_slots": uniq_items,
        "high_slot_names": [x["slot"] for x in uniq_items],
        "reasons": uniq_reasons,
        "escalation": escalation,
        "hints": hints,
        "features": features,
        "mapped": mapped,
        "auto_fix_allowed": False,
        "prefill_applied": (prefill_meta or {}).get("applied") or [],
    }
