"""Compare Validator vs URSim observations."""
from __future__ import annotations

from ai_tool.experimental.ur_program_validator.models import (
    CompareInterpretation,
    CompareResult,
    URSimResult,
    ValidationResult,
    VerificationStatus,
)


def _norm(s: VerificationStatus) -> str:
    if s in ("PASS", "WARNING"):
        return "pass_side"
    if s == "FAIL":
        return "fail_side"
    return "unknown"


def compare_results(
    validator: ValidationResult,
    ur_sim: URSimResult,
    *,
    test_id: str = "",
) -> CompareResult:
    v = validator.status
    u = ur_sim.status

    if v == "FAIL" and u == "FAIL":
        interp: CompareInterpretation = "expected"
        note = "Both static validator and URSim(stub) report failure"
    elif v == "PASS" and u == "PASS":
        interp = "expected"
        note = "Both report success — still not real-robot safety"
    elif v == "FAIL" and u == "PASS":
        interp = "possible_over_validation"
        note = "Validator FAIL but URSim passed — possible over-validation or stub gap"
    elif v in ("PASS", "WARNING") and u == "FAIL":
        interp = "critical_miss"
        note = "CRITICAL: Validator PASS/WARNING but URSim failed — static blind spot"
    else:
        interp = "unknown"
        note = f"Validator={v}, URSim={u} — manual review"

    return CompareResult(
        validator_status=v,
        ur_sim_status=u,
        interpretation=interp,
        note=note,
        test_id=test_id,
    )
