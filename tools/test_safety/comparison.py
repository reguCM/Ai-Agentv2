"""Shadow Gate vs Human expectation comparison (S3 evidence)."""
from __future__ import annotations

from typing import Any

MISMATCH_FALSE_BLOCK = "FALSE_BLOCK"
MISMATCH_FALSE_PASS = "FALSE_PASS"
MISMATCH_WARNING = "WARNING_MISMATCH"
MISMATCH_HUMAN_APPROVAL = "HUMAN_APPROVAL_MISMATCH"
MISMATCH_NONE = "NO_MISMATCH"


def classify_mismatch(
    *,
    shadow_gate_decision: str,
    human_decision: str,
    human_approval_required_shadow: bool,
    human_approval_required_expected: bool | None,
    warnings: list[str],
    warnings_expected_nonempty: bool | None,
) -> str:
    if shadow_gate_decision == "BLOCKED" and human_decision == "PASS":
        return MISMATCH_FALSE_BLOCK
    if shadow_gate_decision == "PASS" and human_decision == "BLOCKED":
        return MISMATCH_FALSE_PASS
    if human_approval_required_expected is not None:
        if human_approval_required_shadow != human_approval_required_expected:
            return MISMATCH_HUMAN_APPROVAL
    if warnings_expected_nonempty is not None:
        nonempty = bool(warnings)
        if nonempty != warnings_expected_nonempty:
            return MISMATCH_WARNING
    return MISMATCH_NONE


def build_comparison_evidence(
    *,
    reference_case_id: str,
    validator_result: dict[str, Any],
    shadow_gate_packet: dict[str, Any],
    expectation: dict[str, Any],
    actual_execution: str = "NOT_EXECUTED",
    actual_result: str = "NOT_RUN",
) -> dict[str, Any]:
    human_decision = str(expectation.get("human_decision") or "PASS")
    shadow_decision = str(shadow_gate_packet.get("gate_decision") or "BLOCKED")
    warnings = list(shadow_gate_packet.get("warnings") or [])
    mismatch = classify_mismatch(
        shadow_gate_decision=shadow_decision,
        human_decision=human_decision,
        human_approval_required_shadow=bool(shadow_gate_packet.get("human_approval_required")),
        human_approval_required_expected=expectation.get("human_approval_required"),
        warnings=warnings,
        warnings_expected_nonempty=expectation.get("warnings_nonempty"),
    )
    match = mismatch == MISMATCH_NONE and shadow_decision == str(
        expectation.get("shadow_gate_decision") or human_decision
    )
    return {
        "reference_case_id": reference_case_id,
        "validator_result": validator_result,
        "shadow_gate_decision": shadow_decision,
        "human_decision": human_decision,
        "expected_shadow_gate_decision": expectation.get("shadow_gate_decision"),
        "actual_execution": actual_execution,
        "actual_result": actual_result,
        "warnings": warnings,
        "shadow_gate_packet": shadow_gate_packet,
        "mismatch": mismatch,
        "match": match,
        "execution_authoritative": False,
        "reason": expectation.get("reason") or "",
    }
