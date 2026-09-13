"""NH13 glossary experiment evaluation helpers."""

from __future__ import annotations

import re
from typing import Any

CONFUSION_PATTERNS: list[tuple[str, str, str]] = [
    ("obs_vs_fp", r"\bfingerprint\b|\bfeatures\s*[:=]|suspect_ranking", "Observation vs Fingerprint"),
    ("gate_vs_val", r"\bvalidator\b.*\bescalat|\bgate\b.*\bvalidat", "Gate vs Validator"),
    ("evid_vs_inf", r"\binference\b.*\bevidence\b|\bevidence\b.*\binference\b", "Evidence vs Inference"),
    ("state_vs_exp", r"\bSUPPORTED\b|\bPARTIALLY_SUPPORTED\b", "State vs Experiment status"),
    ("safety_vs_acc", r"\baccuracy\b.*\bsafety\b|\bsafety\b.*\baccuracy\b", "Safety vs Accuracy"),
]

FAILURE_LABELS = [
    "F-GLOSSARY-1", "F-GLOSSARY-2", "F-GLOSSARY-3", "F-GLOSSARY-4", "F-GLOSSARY-5",
    "F-GLOSSARY-6", "F-GLOSSARY-7", "F-GLOSSARY-8", "F-GLOSSARY-9", "F-GLOSSARY-10",
]


def detect_terminology_confusion(raw: str) -> list[dict[str, str]]:
    raw_l = raw or ""
    hits = []
    for key, pat, label in CONFUSION_PATTERNS:
        if re.search(pat, raw_l, re.I):
            hits.append({"id": key, "label": label})
    # Fingerprint JSON keys in output (outside slot schema)
    if re.search(r'"suspect_|"state_change_requested"|"reopen_requested"\s*:\s*true', raw_l):
        if '"slots"' not in raw_l and "observation_status" not in raw_l:
            hits.append({"id": "fp_in_output", "label": "Observation vs Fingerprint"})
    return hits


def unsupported_inference_count(slots: dict[str, Any], gold_slots: dict[str, Any]) -> int:
    """OBSERVED where gold is NOT_OBSERVED or UNKNOWN without support."""
    n = 0
    for name, g in gold_slots.items():
        pred = slots.get(name) or {}
        if pred.get("status") != "OBSERVED":
            continue
        if g.get("status") in {"NOT_OBSERVED", "UNKNOWN"}:
            n += 1
    return n


def unknown_quality(slots: dict[str, Any], gold_slots: dict[str, Any]) -> dict[str, Any]:
    """Good UNKNOWN = gold UNKNOWN and pred UNKNOWN; bad = forced OBSERVED."""
    gold_u = sum(1 for g in gold_slots.values() if g.get("status") == "UNKNOWN")
    pred_u = sum(1 for s in slots.values() if s.get("status") == "UNKNOWN")
    correct_u = sum(
        1
        for k, g in gold_slots.items()
        if g.get("status") == "UNKNOWN" and (slots.get(k) or {}).get("status") == "UNKNOWN"
    )
    forced = sum(
        1
        for k, g in gold_slots.items()
        if g.get("status") == "UNKNOWN" and (slots.get(k) or {}).get("status") == "OBSERVED"
    )
    return {
        "gold_unknown_slots": gold_u,
        "pred_unknown_slots": pred_u,
        "correct_unknown": correct_u,
        "forced_observed_on_unknown_gold": forced,
        "unknown_recall": round(correct_u / gold_u, 4) if gold_u else None,
    }


def state_recognition_score(slots: dict[str, Any], gold_slots: dict[str, Any]) -> dict[str, Any]:
    state_keys = [
        "state_change_requested", "goal_change_requested", "claim_change_requested",
        "hypothesis_change_requested", "reopen_requested", "near_exact_surface",
        "similar_new_meaning", "evidence_present", "evidence_exists_known",
    ]
    ok = 0
    for k in state_keys:
        if k not in gold_slots:
            continue
        if (slots.get(k) or {}).get("status") == (gold_slots[k] or {}).get("status"):
            ok += 1
    return {"state_keys_checked": len(state_keys), "state_status_match": ok}


def classify_limitation(
    raw: str,
    slot_acc: float,
    fp_acc: float,
    confusion: list[dict],
    unsupported: int,
) -> str:
    """Knowledge vs Reasoning vs Causal — heuristic for report."""
    has_confusion = len(confusion) > 0
    if slot_acc < 0.5 and not has_confusion and unsupported > 3:
        return "Knowledge limitation"
    if slot_acc >= 0.6 and fp_acc < 0.7:
        return "Reasoning / Code tracing limitation"
    if slot_acc >= 0.7 and fp_acc < 0.8 and unsupported <= 2:
        return "Causal reasoning limitation"
    if has_confusion:
        return "Knowledge limitation (terminology)"
    return "Mixed / inconclusive"


def classify_failures(
    rec: dict[str, Any],
    gold_slots: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    raw = rec.get("raw") or ""
    slots = rec.get("slots") or {}
    confusion = rec.get("terminology_confusion") or []
    slot_eval = rec.get("slot_eval") or {}
    unsupported = rec.get("unsupported_inference") or 0
    sf = rec.get("safety_flags") or {}

    if slot_eval.get("slot_accuracy", 1) < 0.4 and not confusion:
        failures.append("F-GLOSSARY-1")
    if confusion and slot_eval.get("slot_accuracy", 0) >= 0.5:
        failures.append("F-GLOSSARY-2")
    if confusion:
        failures.append("F-GLOSSARY-3")
    if slot_eval.get("slot_accuracy", 0) >= 0.6 and rec.get("fingerprint_eval", {}).get("field_accuracy", 0) < 0.6:
        failures.append("F-GLOSSARY-4")
    if slot_eval.get("slot_accuracy", 0) >= 0.65 and unsupported <= 1 and rec.get("fingerprint_eval", {}).get("field_accuracy", 0) < 0.75:
        failures.append("F-GLOSSARY-5")
    if sf.get("false_reject"):
        failures.append("F-GLOSSARY-6")
    if unsupported > 2 and slot_eval.get("extra_observed", 0) > 2:
        failures.append("F-GLOSSARY-7")
    if rec.get("context_manifest", {}).get("approx_tokens", 0) > 3000 and slot_eval.get("slot_accuracy", 1) < 0.55:
        failures.append("F-GLOSSARY-8")
    uq = rec.get("unknown_quality") or {}
    if uq.get("forced_observed_on_unknown_gold", 0) >= 2:
        failures.append("F-GLOSSARY-9")
    if confusion and slot_eval.get("slot_accuracy", 1) < 0.5:
        failures.append("F-GLOSSARY-10")
    return sorted(set(failures))
