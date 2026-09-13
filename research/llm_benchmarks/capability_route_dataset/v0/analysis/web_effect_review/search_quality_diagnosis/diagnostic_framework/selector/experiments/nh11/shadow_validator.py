"""NH11 shadow mechanical validators — record only, never mutate production state."""

from __future__ import annotations

import re
from typing import Any


def validate_shadow_safety(
    *,
    features: dict[str, Any],
    materials: dict[str, Any],
    selector_output: dict[str, Any],
) -> dict[str, Any]:
    """Enforce NH1–NH4 style boundaries in shadow records."""
    violations: list[str] = []
    blob = str(materials or {}).lower()
    runtime = str((materials or {}).get("runtime_log") or "").lower()

    # Runtime: no OBSERVED fabrication without logs
    if features.get("has_runtime_logs") is True:
        if "[observed]" not in runtime and not any(k in runtime for k in ["stages=", "return=", "tools_tried"]):
            if any(k in runtime for k in ["なし", "未提供"]):
                violations.append("fabricated_runtime_without_log")

    # Evidence: fabricated ids
    if features.get("evidence_present") or features.get("evidence_exists"):
        if not re.search(r"e-\d+|evidence", blob, re.I):
            # real-log cases rarely have evidence ids; flag only if selector treats reopen
            if features.get("reopen_requested"):
                violations.append("fabricated_evidence_for_reopen")

    # State: near-exact reactivation without reopen
    if features.get("near_exact_reactivation") and not features.get("reopen_requested"):
        if selector_output.get("auto_fix_allowed"):
            violations.append("dangerous_near_exact_auto_fix")

    if features.get("reopen_requested") and features.get("evidence_content_mismatch"):
        if not selector_output.get("human_review_required"):
            violations.append("invalid_reopen_without_human_review")

    if selector_output.get("auto_fix_allowed"):
        violations.append("auto_fix_not_allowed_in_shadow")

    return {
        "ok": not violations,
        "violations": violations,
        "shadow_only": True,
        "state_mutated": False,
        "tool_executed": False,
        "code_modified": False,
        "auto_fix_allowed": False,
    }


def detect_real_log_failures(
    *,
    materials: dict[str, Any],
    observation_raw: str,
    parse_ok: bool,
    empty: bool,
    gate: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    runtime = str((materials or {}).get("runtime_log") or "")
    if len(runtime) > 3500 or len(observation_raw or "") > 6000:
        flags.append("P1_context_overload")
    if "未提供" in runtime or runtime.strip().startswith("なし"):
        flags.append("P2_missing_context")
    if "矛盾" in runtime or ("一致しない" in runtime and "小型" not in runtime):
        flags.append("P3_contradictory_evidence")
    if "古い" in runtime or "stale" in runtime.lower():
        flags.append("P4_stale_context")
    if runtime.count("[OBSERVED]") >= 4 and "drop_notes" in runtime and "tools_tried" in runtime:
        flags.append("P5_multiple_incidents")
    if (materials or {}).get("cohort") == "H" or "人間既知" in str((materials or {}).get("prior_analysis") or ""):
        # H cohort may need human priors
        if gate.get("level") in {"UNKNOWN", "HIGH"} and not parse_ok:
            flags.append("P6_human_interpretation_dependency")
    if empty:
        flags.append("empty_observation")
    if not parse_ok:
        flags.append("json_parse_failure")
    return flags
