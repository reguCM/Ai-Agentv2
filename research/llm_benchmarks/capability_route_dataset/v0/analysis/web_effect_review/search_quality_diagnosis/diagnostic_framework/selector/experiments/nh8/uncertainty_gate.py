"""NH8 mechanical uncertainty gate. LLM does not choose escalation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RULES_PATH = Path(__file__).resolve().parent / "rules.json"


def load_rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def _blob(materials: dict[str, Any]) -> str:
    return json.dumps(materials or {}, ensure_ascii=False).lower()


def material_hints(materials: dict[str, Any]) -> dict[str, bool]:
    b = _blob(materials)
    runtime = str((materials or {}).get("runtime_log") or "").lower()
    prior = str((materials or {}).get("prior_analysis") or "").lower()
    summary = str((materials or {}).get("problem_summary") or "").lower()
    state = str((materials or {}).get("state_context") or "").lower()
    evid = str((materials or {}).get("evidence") or "").lower()
    history = str((materials or {}).get("state_history") or "").lower()
    return {
        "mentions_reopen": "reopen" in b
        and not any(
            n in b.replace(" ", "")
            for n in ["reopenではなく", "reopen要求ではない", "notareopen"]
        ),
        "mentions_state_update": any(
            k in b
            for k in [
                "change request",
                "更新要求",
                "active 化",
                "active化",
                "goal 更新",
                "reopen",
            ]
        )
        and not any(k in state for k in ["変更要求はない", "変更なし", "state 変更なし", "state/evidence 変更なし"]),
        "mentions_no_state": any(
            k in state + summary
            for k in ["変更要求はない", "変更なし", "state 変更なし", "state/evidence 変更なし"]
        ),
        "mentions_evidence_id": bool(re.search(r"e-\d+|evidence_id", b, re.I)),
        "mentions_content_mismatch": (
            "一致しない" in evid + summary or "unrelated" in evid
        )
        and bool(re.search(r"e-\d+|evidence", evid + summary, re.I)),
        "mentions_disagreement": (
            ("小型" in b and "大型" in b)
            and any(k in summary + prior for k in ["一致しない", "不一致"])
        ),
        "mentions_small_unverified": (
            ("断定" in prior or "only root cause" in prior)
            and ("小型" in prior or "small llm" in prior)
        ),
        "runtime_none": any(k in runtime for k in ["なし", "未提供", "no log"]) and "[observed]" not in runtime,
        "runtime_observed": "[observed]" in runtime,
        "code_only_no_runtime": (
            bool((materials or {}).get("code_excerpt"))
            and any(k in runtime for k in ["なし", "未提供"])
        ),
        "mentions_near_exact": any(k in b for k in ["句読点", "unicode", "case 差", "正規化/case"]),
        "mentions_similar_new": any(k in b for k in ["対象機能が異なる", "新しい意味"]),
    }


def evaluate_uncertainty(
    *,
    materials: dict[str, Any],
    observation: dict[str, Any],
    mapped: dict[str, Any],
    parse_ok: bool,
    empty_output: bool,
) -> dict[str, Any]:
    hints = material_hints(materials)
    features = dict((mapped or {}).get("features") or {})
    slots = dict((mapped or {}).get("slots") or {})
    obs = observation or {}
    inf = " ".join(str(x) for x in (obs.get("inferences_not_facts") or [])).lower()
    prior = json.dumps(obs.get("prior_analysis_notes") or [], ensure_ascii=False).lower()
    reasons: list[str] = []

    if empty_output or not parse_ok:
        reasons.append("parse_or_empty")
    if obs.get("hallucinated_feature_keys"):
        reasons.append("feature_name_hallucination")

    if hints["mentions_state_update"] and features.get("state_change_requested") is not True:
        reasons.append("state_hint_missing_in_fingerprint")
    if hints["mentions_reopen"] and features.get("reopen_requested") is not True:
        reasons.append("reopen_hint_missing_in_fingerprint")
    if hints["mentions_evidence_id"] and features.get("evidence_present") is not True and features.get("evidence_exists") is not True:
        reasons.append("evidence_id_hint_missing")
    if hints["mentions_content_mismatch"] and features.get("evidence_content_mismatch") is not True:
        reasons.append("content_mismatch_hint_missing")
    if hints["mentions_disagreement"] and features.get("llm_disagreement") is not True:
        reasons.append("disagreement_hint_missing")
    if hints["mentions_small_unverified"] and features.get("small_llm_output_suspicious") is not True:
        reasons.append("small_llm_unverified_hint_missing")
    if hints["runtime_none"] and features.get("has_runtime_logs") is True:
        reasons.append("runtime_none_but_logs_true")
    if hints["runtime_observed"] and features.get("has_runtime_logs") is False:
        reasons.append("runtime_observed_but_logs_false")
    if features.get("near_exact_reactivation") and features.get("similar_but_new_goal"):
        reasons.append("near_exact_and_similar_new")
    if hints["code_only_no_runtime"] and features.get("has_runtime_logs") is not False:
        reasons.append("insufficient_runtime_with_code_only")
    if slots.get("reopen_present") and "reopen ではなく" in prior:
        reasons.append("mapping_reopen_ambiguity")

    if (
        hints["mentions_disagreement"]
        and any(k in inf for k in ["一致しない", "不一致", "判断"])
        and not (
            ("一致しない" in prior or "不一致" in prior)
            and ("大型" in prior or "large" in prior)
        )
    ):
        reasons.append("disagreement_in_inference_bucket")

    level = "HIGH" if reasons else "LOW"
    return {
        "level": level,
        "reasons": reasons,
        "escalation": "LARGE_LLM" if level == "HIGH" else "NONE",
        "hints": hints,
    }


def merge_features_safely(small_feat: dict[str, bool], large_feat: dict[str, bool]) -> dict[str, bool]:
    rules = load_rules()
    keep = set(rules.get("large_cannot_clear_safety_flags") or [])
    out = dict(large_feat)
    for k in keep:
        if small_feat.get(k) is True:
            out[k] = True
    return out


def apply_material_safety_locks(features: dict[str, bool], materials: dict[str, Any]) -> dict[str, bool]:
    """Mechanical locks from materials. Does not invent presence."""
    hints = material_hints(materials)
    out = dict(features)
    if hints["runtime_none"]:
        out["has_runtime_logs"] = False
    return out
