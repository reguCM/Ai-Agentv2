"""NH14 shadow pipeline — mechanical only, no LLM."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

FRAMEWORK = Path(__file__).resolve().parents[3]
NH9 = FRAMEWORK / "selector" / "experiments" / "nh9"
NH10 = FRAMEWORK / "selector" / "experiments" / "nh10"
NH11 = FRAMEWORK / "selector" / "experiments" / "nh11"
NH12_2 = FRAMEWORK / "selector" / "experiments" / "nh12_2"

for p in (NH9, NH10, NH11, NH12_2):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fixed_slots import CORE, map_slots_to_features, unknown_rate  # noqa: E402
from mechanical_compression import compress_materials  # noqa: E402
from map_to_observation import map_compression_to_observation_slots  # noqa: E402
from mechanical_prefill import apply_mechanical_prefill  # noqa: E402
from shadow_gate import evaluate_shadow_gate  # noqa: E402
from shadow_validator import detect_real_log_failures, validate_shadow_safety  # noqa: E402


def nh14_gate(gate: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    """Remap NH11 gate to NH14 external-help semantics (no Large LLM)."""
    out = dict(gate)
    level = gate.get("level") or "UNKNOWN"
    reasons = list(gate.get("reasons") or [])

    if not validation.get("ok", True):
        out["nh14_level"] = "VALIDATION_REJECT"
        out["nh14_escalation"] = "STOP"
        out["nh14_route"] = "VALIDATION_REJECT"
        reasons.append("validation_reject")
    elif level == "LOW":
        out["nh14_level"] = "LOW"
        out["nh14_escalation"] = "NONE"
        out["nh14_route"] = "SELF_RESOLVED"
    elif level in {"MEDIUM", "HIGH"}:
        out["nh14_level"] = level
        out["nh14_escalation"] = "EXTERNAL_HELP"
        out["nh14_route"] = "EXTERNAL_HELP"
        reasons.append("gate_not_low")
    else:
        out["nh14_level"] = "UNKNOWN"
        out["nh14_escalation"] = "EXTERNAL_HELP"
        out["nh14_route"] = "UNKNOWN"
        reasons.append("insufficient_evidence_or_context")

    out["nh14_reasons"] = list(dict.fromkeys(reasons))
    out["large_llm_skipped"] = True
    out["auto_fix_allowed"] = False
    return out


def observation_coverage(slots: dict[str, Any]) -> dict[str, Any]:
    core = [k for k in CORE if k in slots]
    known = sum(1 for k in core if (slots.get(k) or {}).get("status") != "UNKNOWN")
    return {
        "core_slots": len(core),
        "core_observed": known,
        "coverage": round(known / len(core), 4) if core else 0.0,
        "unknown_rate": unknown_rate(slots),
    }


def flatten_observation(slots: dict[str, Any]) -> dict[str, Any]:
    """Simple observation dict for external packages — no inference."""
    out: dict[str, Any] = {}
    for name, item in (slots or {}).items():
        st = (item or {}).get("status")
        if st == "UNKNOWN":
            continue
        out[name] = {
            "status": st,
            "value": (item or {}).get("value"),
            "evidence_reference": (item or {}).get("evidence_reference") or "",
        }
    return out


def run_shadow_pipeline(
    case: dict[str, Any],
    selector: Any,
) -> dict[str, Any]:
    materials = case.get("materials") or {}
    compressed = compress_materials(materials)
    mapped_obs = map_compression_to_observation_slots(compressed)
    slots = mapped_obs.get("slots") if isinstance(mapped_obs, dict) and "slots" in mapped_obs else mapped_obs
    prefill = apply_mechanical_prefill(slots, materials)
    slots2 = prefill.get("slots") or slots
    mapped = map_slots_to_features(slots2, materials)
    features = mapped.get("features") or {}
    gate_base = evaluate_shadow_gate(
        slots=slots2,
        materials=materials,
        mapped=mapped,
        prefill_meta=prefill,
    )
    from fingerprint_utils import build_selector_case  # noqa: E402

    meta = {"case_id": case.get("case_id"), "scenario": case.get("scenario")}
    sel_out = selector.select(build_selector_case(meta, features))
    sel_out["auto_fix_allowed"] = False
    sel_out["shadow_mode"] = True
    sel_out["executed"] = False
    validation = validate_shadow_safety(
        features=features,
        materials=materials,
        selector_output=sel_out,
    )
    gate = nh14_gate(gate_base, validation)
    real_flags = detect_real_log_failures(
        materials=materials,
        observation_raw="",
        parse_ok=True,
        empty=False,
        gate=gate_base,
    )
    cov = observation_coverage(slots2)
    return {
        "case_id": case.get("case_id"),
        "cohort": case.get("cohort"),
        "types": case.get("types") or case.get("type_tags"),
        "compression": compressed,
        "observation_mapping": mapped_obs,
        "observation_slots": slots2,
        "observation_flat": flatten_observation(slots2),
        "prefill": prefill,
        "fingerprint": {"features": features, "uncertainties": mapped.get("uncertainties") or []},
        "gate": gate,
        "gate_base": gate_base,
        "validation": validation,
        "selector_output": sel_out,
        "real_log_flags": real_flags,
        "observation_coverage": cov,
        "final_classification": gate.get("nh14_route"),
        "auto_fix_allowed": False,
        "shadow_mode": True,
        "production_mutations": 0,
    }
