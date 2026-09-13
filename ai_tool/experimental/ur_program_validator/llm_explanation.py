"""LLM-facing explanation — uses observations, does not replace validator."""
from __future__ import annotations

from typing import Any

from ai_tool.experimental.ur_program_validator.models import CompareResult, URSimResult, ValidationResult


def explain_validation(
    validator: ValidationResult,
    ur_sim: URSimResult | None,
    compare: CompareResult | None,
    *,
    test_id: str = "",
) -> str:
    """Conversation material for LLM — not mechanical ground truth."""
    lines = [f"## URScript Validation Explanation ({test_id})"]
    lines.append(f"Validator overall: **{validator.status}**")
    if validator.issues:
        lines.append("### Validator issues")
        for iss in validator.issues[:8]:
            lines.append(f"- [{iss.status}] line {iss.line} {iss.kind.value}: {iss.message}")
    else:
        lines.append("Validator: no issues in catalog scope.")

    lines.append("### Not validated by static checker")
    for n in validator.not_validated[:5]:
        lines.append(f"- {n}")

    if ur_sim:
        lines.append(f"### URSim ({ur_sim.mode})")
        lines.append(f"Status: {ur_sim.status} — {ur_sim.message}")
        for e in ur_sim.errors:
            lines.append(f"- {e}")

    if compare:
        lines.append(f"### Validator vs URSim: {compare.interpretation}")
        lines.append(compare.note)
        if compare.interpretation == "critical_miss":
            lines.append(
                "**Important:** Static validation passed but simulation failed. "
                "Do not treat validator PASS as runtime correctness."
            )

    lines.append(
        "### Boundary\n"
        "Official Specification → Static Validation → Simulation → Real Robot. "
        "This PoC stops at simulation stub; real robot safety not verified."
    )
    return "\n".join(lines)


def format_for_llm_context(
    validator: ValidationResult,
    ur_sim: URSimResult,
    compare: CompareResult,
    suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "validator_result": validator.to_dict(),
        "ursim_result": ur_sim.to_dict(),
        "compare": compare.to_dict(),
        "fix_suggestions": suggestions,
        "llm_role": "explain_observations_not_decide_truth",
        "provenance_note": "Use official catalog + validator + URSim observations — not LLM memory alone",
    }
