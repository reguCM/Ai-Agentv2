"""NH6 fingerprint parsing and evaluation utilities (experimental)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent / "feature_schema.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_features() -> list[str]:
    return list(load_json(SCHEMA_PATH)["features"].keys())


def extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
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


def normalize_llm_fingerprint(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Map LLM output to NH5 selector features. Omit unknown/null booleans."""
    allowed = set(allowed_features())
    out_features: dict[str, bool] = {}
    uncertainties: list[str] = list(raw.get("uncertainties") or []) if raw else []
    raw_features = (raw or {}).get("features") or {}

    for key, val in raw_features.items():
        if key not in allowed:
            continue
        if val is None:
            if key not in uncertainties:
                uncertainties.append(key)
            continue
        if isinstance(val, bool):
            out_features[key] = val
        elif isinstance(val, str):
            low = val.strip().lower()
            if low in {"true", "yes"}:
                out_features[key] = True
            elif low in {"false", "no"}:
                out_features[key] = False
            elif low in {"unknown", "null", "uncertain"}:
                if key not in uncertainties:
                    uncertainties.append(key)
            else:
                if key not in uncertainties:
                    uncertainties.append(key)

    evidence = (raw or {}).get("evidence_classification") or {}
    return {
        "features": out_features,
        "uncertainties": sorted(set(uncertainties)),
        "evidence_classification": {
            "facts": list(evidence.get("facts") or []),
            "observed": list(evidence.get("observed") or []),
            "inference": list(evidence.get("inference") or []),
            "unknown": list(evidence.get("unknown") or []),
        },
        "raw_llm": raw,
    }


def evaluate_fingerprint(
    gold_features: dict[str, bool],
    llm_norm: dict[str, Any],
    *,
    case_id: str,
) -> dict[str, Any]:
    """Step 1: compare gold vs LLM fingerprint."""
    llm_features = llm_norm.get("features") or {}
    uncertainties = set(llm_norm.get("uncertainties") or [])
    field_results: list[dict[str, Any]] = []
    correct = partial = error = unknown_ok = unsupported = 0

    for key, gold_val in gold_features.items():
        llm_val = llm_features.get(key)
        if key in uncertainties or (key not in llm_features and gold_val is True):
            if gold_val is False and key not in llm_features:
                status = "correct_absent"
                correct += 1
            elif gold_val is True:
                status = "miss_or_unknown"
                error += 1
            else:
                status = "unknown_as_stated"
                unknown_ok += 1
        elif llm_val == gold_val:
            status = "correct"
            correct += 1
        else:
            status = "error"
            error += 1
        field_results.append(
            {"field": key, "gold": gold_val, "llm": llm_val, "status": status}
        )

    for key, llm_val in llm_features.items():
        if key not in gold_features and llm_val is True:
            unsupported += 1
            field_results.append(
                {
                    "field": key,
                    "gold": None,
                    "llm": llm_val,
                    "status": "unsupported_inference",
                }
            )

    total_gold = len(gold_features)
    accuracy = correct / total_gold if total_gold else 1.0

    failure_flags = {
        "F1_phantom_info": unsupported > 0
        or any(
            fr["status"] == "error"
            and fr["gold"] is False
            and fr.get("llm") is True
            for fr in field_results
        ),
        "F2_state_change_miss": gold_features.get("state_change_requested") is True
        and llm_features.get("state_change_requested") is not True,
        "F3_evidence_miss": any(
            gold_features.get(k) is True and llm_features.get(k) is not True
            for k in (
                "evidence_suspicious",
                "evidence_content_mismatch",
                "evidence_present",
                "evidence_exists",
            )
        ),
        "F6_no_unknown": gold_features.get("has_runtime_logs") is False
        and llm_features.get("has_runtime_logs") is True,
    }

    return {
        "case_id": case_id,
        "field_results": field_results,
        "field_accuracy": round(accuracy, 4),
        "correct_fields": correct,
        "partial_or_unknown_ok": unknown_ok,
        "error_fields": error,
        "unsupported_inference_count": unsupported,
        "unknown_precision_note": f"uncertainties={sorted(uncertainties)}",
        "failure_flags": failure_flags,
    }


def build_selector_case(case_meta: dict[str, Any], features: dict[str, bool]) -> dict[str, Any]:
    return {
        "case_id": case_meta["case_id"],
        "scenario": case_meta["scenario"],
        "safety_class": case_meta.get("safety_class", "UNKNOWN"),
        "description": case_meta.get("description", ""),
        "features": features,
    }
