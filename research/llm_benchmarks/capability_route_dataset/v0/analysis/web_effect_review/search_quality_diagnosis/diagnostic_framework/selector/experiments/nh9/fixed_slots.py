"""NH9 fixed-slot parse, mapping, gate, and large-correction validation."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

NH9 = Path(__file__).resolve().parent
NH8 = NH9.parent / "nh8"
sys.path.insert(0, str(NH8))

from uncertainty_gate import apply_material_safety_locks, evaluate_uncertainty, material_hints  # noqa: E402

SLOTS = json.loads((NH9 / "slots.json").read_text(encoding="utf-8"))["slots"]
CORE = json.loads((NH9 / "slots.json").read_text(encoding="utf-8"))["core_slots"]
STATUSES = {"OBSERVED", "NOT_OBSERVED", "UNKNOWN"}


def extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def empty_slot(status: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "status": status,
        "value": None,
        "confidence": "low" if status == "UNKNOWN" else "high",
        "evidence_reference": "",
    }


def normalize_slots(raw: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = raw or {}
    inner = raw.get("slots") if isinstance(raw.get("slots"), dict) else raw
    out: dict[str, dict[str, Any]] = {}
    for name in SLOTS:
        item = inner.get(name) if isinstance(inner, dict) else None
        if item is None:
            out[name] = empty_slot("UNKNOWN")
            continue
        if isinstance(item, str):
            st = item.strip().upper().replace(" ", "_")
            if st in STATUSES:
                val = True if st == "OBSERVED" else False if st == "NOT_OBSERVED" else None
                out[name] = {
                    "status": st,
                    "value": val,
                    "confidence": "medium",
                    "evidence_reference": "",
                }
                continue
        if isinstance(item, bool):
            out[name] = {
                "status": "OBSERVED" if item else "NOT_OBSERVED",
                "value": item,
                "confidence": "medium",
                "evidence_reference": "",
            }
            continue
        if isinstance(item, dict):
            st = str(item.get("observation_status") or item.get("status") or "UNKNOWN").upper()
            if st not in STATUSES:
                st = "UNKNOWN"
            val = item.get("value")
            if st == "NOT_OBSERVED" and val is None:
                val = False
            if st == "UNKNOWN":
                val = None
            out[name] = {
                "status": st,
                "value": val,
                "confidence": item.get("confidence") or ("low" if st == "UNKNOWN" else "medium"),
                "evidence_reference": str(item.get("evidence_reference") or item.get("evidence") or ""),
            }
            continue
        out[name] = empty_slot("UNKNOWN")
    return out


def status(slots: dict[str, dict[str, Any]], name: str) -> str:
    return str((slots.get(name) or {}).get("status") or "UNKNOWN")


def observed_true(slots: dict[str, dict[str, Any]], name: str) -> bool:
    s = slots.get(name) or {}
    return s.get("status") == "OBSERVED" and s.get("value") is True


def observed_false(slots: dict[str, dict[str, Any]], name: str) -> bool:
    s = slots.get(name) or {}
    if s.get("status") == "NOT_OBSERVED":
        return True
    return s.get("status") == "OBSERVED" and s.get("value") is False


def map_slots_to_features(slots: dict[str, dict[str, Any]], materials: dict[str, Any] | None = None) -> dict[str, Any]:
    features: dict[str, bool] = {}
    trace: list[str] = []
    derived: dict[str, Any] = {}
    unknowns: list[str] = []

    state = any(
        observed_true(slots, k)
        for k in (
            "state_change_requested",
            "goal_change_requested",
            "claim_change_requested",
            "hypothesis_change_requested",
            "reopen_requested",
        )
    )
    no_state = all(
        observed_false(slots, k)
        for k in (
            "state_change_requested",
            "goal_change_requested",
            "claim_change_requested",
            "hypothesis_change_requested",
        )
    )
    if state:
        features["state_change_requested"] = True
        trace.append("state/goal/claim/hypothesis/reopen OBSERVED → state_change_requested")
    elif no_state:
        features["state_change_requested"] = False

    if observed_true(slots, "reopen_requested"):
        features["reopen_requested"] = True
    elif observed_false(slots, "reopen_requested") or no_state:
        features["reopen_requested"] = False

    if observed_true(slots, "stdout_present") or observed_true(slots, "runtime_issue_observed"):
        features["has_runtime_logs"] = True
    elif observed_false(slots, "stdout_present") and observed_false(slots, "runtime_issue_observed"):
        features["has_runtime_logs"] = False

    if observed_true(slots, "code_scope_present"):
        features["code_available"] = True
    elif observed_false(slots, "code_scope_present"):
        features["code_available"] = False

    if observed_true(slots, "code_multi_file"):
        features["needs_path_integration"] = True
        features["needs_local_analysis"] = True
    elif features.get("code_available") and observed_false(slots, "code_multi_file"):
        features["needs_local_analysis"] = True
        features["needs_path_integration"] = False
    elif features.get("code_available"):
        features["needs_local_analysis"] = True

    if features.get("code_available") and (
        status(slots, "caller_scope_present") == "UNKNOWN" or observed_false(slots, "caller_scope_present")
    ):
        features["path_unknown_or_untrusted"] = True
    if features.get("needs_path_integration"):
        features["path_unknown_or_untrusted"] = True

    if observed_true(slots, "near_exact_surface"):
        features["near_exact_reactivation"] = True
    if observed_true(slots, "similar_new_meaning"):
        features["similar_but_new_goal"] = True
    if observed_true(slots, "evidence_present"):
        features["evidence_present"] = True
    if observed_true(slots, "evidence_exists_known"):
        features["evidence_exists"] = True
    if observed_true(slots, "evidence_content_mismatch") or (
        status(slots, "evidence_content_known") == "OBSERVED" and (slots.get("evidence_content_known") or {}).get("value") is False
    ):
        features["evidence_content_mismatch"] = True
        features["evidence_suspicious"] = True
    if observed_true(slots, "small_llm_unverified"):
        features["small_llm_output_suspicious"] = True
    if observed_true(slots, "llm_disagreement"):
        features["llm_disagreement"] = True
    if observed_true(slots, "stdout_present") and observed_true(slots, "llm_handoff_present"):
        features["suspect_stdout_vs_llm_handoff"] = True
    if observed_false(slots, "ranking_filter_separated") and (
        observed_true(slots, "ranking_present") and observed_true(slots, "collect_filter_present")
    ):
        features["suspect_ranking_vs_filter"] = True
    if observed_true(slots, "off_path_cause_mentioned"):
        features["suspect_off_path_causes"] = True

    if status(slots, "evidence_freshness_known") == "UNKNOWN" and observed_true(slots, "evidence_present"):
        features["evidence_timestamp_unknown"] = True
        unknowns.append("evidence_freshness_unknown")

    if features.get("code_available"):
        features.setdefault("suspect_ranking_vs_filter", False)
        features.setdefault("suspect_stdout_vs_llm_handoff", False)
        features.setdefault("suspect_off_path_causes", False)

    derived["state_safety_required"] = bool(features.get("state_change_requested") or features.get("reopen_requested"))
    derived["reopen_validation_required"] = bool(
        features.get("reopen_requested")
        and not (
            observed_true(slots, "evidence_exists_known")
            and status(slots, "evidence_content_known") == "OBSERVED"
        )
    )
    if status(slots, "runtime_issue_observed") == "UNKNOWN" and features.get("code_available"):
        derived["runtime_diagnosis_confidence"] = "HIGH_RISK"
        unknowns.append("runtime_issue_unknown")
    elif features.get("has_runtime_logs") is False:
        derived["runtime_diagnosis_confidence"] = "NO_LOGS"
    else:
        derived["runtime_diagnosis_confidence"] = "LOGS_PRESENT"

    if materials:
        features = apply_material_safety_locks(features, materials)

    return {
        "features": features,
        "mapping_trace": trace,
        "derived": derived,
        "uncertainties": unknowns,
        "slots": slots,
    }


def evaluate_slot_accuracy(gold: dict[str, dict[str, Any]], pred: dict[str, dict[str, Any]]) -> dict[str, Any]:
    keys = CORE
    correct = 0
    extra_obs = 0
    miss_obs = 0
    rows = []
    for k in keys:
        g = gold.get(k) or empty_slot()
        p = pred.get(k) or empty_slot()
        ok = g.get("status") == p.get("status")
        if g.get("status") == "OBSERVED":
            ok = ok and bool(g.get("value")) == bool(p.get("value"))
        if ok:
            correct += 1
        elif p.get("status") == "OBSERVED" and g.get("status") != "OBSERVED":
            extra_obs += 1
        elif g.get("status") == "OBSERVED" and p.get("status") != "OBSERVED":
            miss_obs += 1
        rows.append({"slot": k, "gold": g.get("status"), "pred": p.get("status"), "ok": ok})
    n = len(keys) or 1
    return {
        "slot_accuracy": round(correct / n, 4),
        "correct": correct,
        "extra_observed": extra_obs,
        "miss_observed": miss_obs,
        "rows": rows,
    }


def apply_confidence_gate(slots: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Treat low-confidence OBSERVED as UNKNOWN (ablation: fixed slot + confidence)."""
    out: dict[str, dict[str, Any]] = {}
    for name, item in slots.items():
        cur = dict(item)
        conf = str(cur.get("confidence") or "").lower()
        if cur.get("status") == "OBSERVED" and conf in {"low", "unknown", ""}:
            cur["status"] = "UNKNOWN"
            cur["value"] = None
        out[name] = cur
    return out


def unknown_rate(slots: dict[str, dict[str, Any]], keys: list[str] | None = None) -> float:
    keys = keys or CORE
    n = len(keys) or 1
    return round(sum(1 for k in keys if status(slots, k) == "UNKNOWN") / n, 4)


def extra_slot_names(raw: dict[str, Any] | None, allowed: list[str]) -> list[str]:
    """F7: large filled slots outside the HIGH allow-list."""
    if not raw:
        return []
    inner = raw.get("slots") if isinstance(raw.get("slots"), dict) else raw
    if not isinstance(inner, dict):
        return []
    allow = set(allowed)
    return sorted(k for k in inner if k not in allow and k in SLOTS)


def high_slots(slots: dict[str, dict[str, Any]], materials: dict[str, Any], mapped: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    hints = material_hints(materials)
    high: list[str] = []
    if hints["mentions_state_update"] and not observed_true(slots, "state_change_requested") and not observed_true(slots, "goal_change_requested"):
        high.append("state_change_requested")
    if hints["mentions_reopen"] and not observed_true(slots, "reopen_requested"):
        high.append("reopen_requested")
    if hints["mentions_evidence_id"] and not observed_true(slots, "evidence_present"):
        high.append("evidence_present")
    if hints["mentions_content_mismatch"] and not observed_true(slots, "evidence_content_mismatch"):
        high.append("evidence_content_mismatch")
    if hints["mentions_disagreement"] and not observed_true(slots, "llm_disagreement"):
        high.append("llm_disagreement")
    if hints["mentions_small_unverified"] and not observed_true(slots, "small_llm_unverified"):
        high.append("small_llm_unverified")
    if observed_true(slots, "reopen_requested") and status(slots, "evidence_exists_known") != "OBSERVED":
        high.append("evidence_exists_known")
    if observed_true(slots, "evidence_present") and status(slots, "evidence_content_known") == "UNKNOWN":
        high.append("evidence_content_known")
    if observed_true(slots, "near_exact_surface") and observed_true(slots, "similar_new_meaning"):
        high.extend(["near_exact_surface", "similar_new_meaning"])
    if hints["code_only_no_runtime"] and status(slots, "runtime_issue_observed") == "UNKNOWN":
        high.append("runtime_issue_observed")
    gate = evaluate_uncertainty(
        materials=materials,
        observation={"inferences_not_facts": [], "prior_analysis_notes": [], "hallucinated_feature_keys": []},
        mapped=mapped,
        parse_ok=True,
        empty_output=False,
    )
    # disagreement bucket equivalent: slot unknown while hinted
    if hints["mentions_disagreement"] and status(slots, "llm_disagreement") == "UNKNOWN":
        if "llm_disagreement" not in high:
            high.append("llm_disagreement")
    return sorted(set(high)), gate


def evaluate_fixed_gate(
    *,
    slots: dict[str, dict[str, Any]],
    materials: dict[str, Any],
    mapped: dict[str, Any],
    parse_ok: bool,
    empty_output: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    if empty_output or not parse_ok:
        reasons.append("parse_or_empty")
    hs, base = high_slots(slots, materials, mapped)
    reasons.extend(base.get("reasons") or [])
    for s in hs:
        reasons.append(f"high_slot:{s}")
    # unique preserve order
    seen: set[str] = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    level = "HIGH" if uniq else "LOW"
    return {
        "level": level,
        "reasons": uniq,
        "high_slots": hs,
        "escalation": "LARGE_LLM" if level == "HIGH" else "NONE",
        "hints": base.get("hints") or material_hints(materials),
    }


def validate_large_slots(
    *,
    small_slots: dict[str, dict[str, Any]],
    large_slots: dict[str, dict[str, Any]],
    allowed: list[str],
    materials: dict[str, Any],
) -> dict[str, Any]:
    """Accept large updates only for allowed HIGH slots, with evidence and no fabrication."""
    hints = material_hints(materials)
    blob = json.dumps(materials or {}, ensure_ascii=False).lower()
    merged = {k: dict(v) for k, v in small_slots.items()}
    rejected: list[str] = []
    accepted: list[str] = []
    for name in allowed:
        if name not in SLOTS:
            continue
        cand = large_slots.get(name) or empty_slot()
        if cand.get("status") == "OBSERVED":
            ref = str(cand.get("evidence_reference") or "").strip()
            if not ref:
                rejected.append(f"{name}:observed_without_evidence_reference")
                merged[name] = {**small_slots.get(name, empty_slot()), "status": "UNKNOWN", "value": None}
                continue
            if name in {"runtime_issue_observed", "stdout_present"} and hints["runtime_none"]:
                rejected.append(f"{name}:runtime_fabricated")
                merged[name] = {
                    "status": "NOT_OBSERVED",
                    "value": False,
                    "confidence": "high",
                    "evidence_reference": "materials runtime_log=なし",
                }
                continue
            if name.startswith("evidence") and cand.get("value") is True:
                if not re.search(r"e-\d+|evidence", blob, re.I):
                    rejected.append(f"{name}:evidence_fabricated")
                    merged[name] = empty_slot("UNKNOWN")
                    continue
            if name == "llm_disagreement" and not hints["mentions_disagreement"]:
                rejected.append(f"{name}:disagreement_not_in_materials")
                continue
        merged[name] = cand
        accepted.append(name)
    # large cannot clear small OBSERVED safety slots
    for name in (
        "state_change_requested",
        "reopen_requested",
        "evidence_content_mismatch",
        "llm_disagreement",
        "near_exact_surface",
    ):
        if observed_true(small_slots, name) and not observed_true(merged, name):
            merged[name] = small_slots[name]
            rejected.append(f"{name}:cannot_clear_small_observed")
    return {"slots": merged, "accepted": accepted, "rejected": rejected}


def slot_schema_prompt_block() -> str:
    lines = []
    for name in SLOTS:
        lines.append(f'    "{name}": {{"status": "OBSERVED|NOT_OBSERVED|UNKNOWN", "value": true|false|null, "confidence": "low|medium|high", "evidence_reference": "quote or empty"}}')
    return "{\n  \"slots\": {\n" + ",\n".join(lines) + "\n  }\n}"
