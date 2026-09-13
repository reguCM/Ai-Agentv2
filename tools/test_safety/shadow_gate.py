"""S3 — Shadow Gate (PASS | BLOCKED only; non-authoritative)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GATE_ID = "test_safety_shadow_gate_s3_v1"
SUPPORTED_EVALUATION_SCHEMA_VERSIONS = frozenset({"1"})
INVALID_GATE_REASON = "INVALID_OR_UNVERIFIED_EVALUATION"

# Dimension states that forbid automatic execution without human review (policy).
PROHIBITED_AUTOMATIC_PASS: tuple[tuple[str, str], ...] = (
    ("credentials", "PRESENT"),
)


def _human_approval_flags(
    evaluation: dict[str, Any],
) -> tuple[bool, str]:
    dims = evaluation.get("safety_dimensions") or {}
    primary = str(evaluation.get("primary_risk_level") or "LEVEL_1")
    human = False
    reason = ""
    if primary == "LEVEL_3" and dims.get("llm") == "PRESENT":
        human = True
        reason = "LEVEL_3_live_llm_condition_dependent"
    if dims.get("git_operation") == "PRESENT":
        human = True
        reason = "git_operation_in_plan"
    if dims.get("external_service") == "PRESENT":
        human = True
        reason = "external_service"
    if dims.get("network") == "PRESENT":
        human = True
        reason = "uncontrolled_network"
    if dims.get("repository_outside_write") == "PRESENT":
        human = True
        reason = "repository_outside_write"
    return human, reason


def _postflight_required(evaluation: dict[str, Any]) -> bool:
    if evaluation.get("postflight_git_check_required") is True:
        return True
    dims = evaluation.get("safety_dimensions") or {}
    primary = str(evaluation.get("primary_risk_level") or "LEVEL_1")
    return (
        dims.get("filesystem_write") == "PRESENT"
        or dims.get("git_operation") in ("PRESENT", "UNKNOWN")
        or primary == "LEVEL_3"
    )


def decide_gate_from_evaluation(
    evaluation: dict[str, Any],
    *,
    validator_warnings: list[str] | None = None,
) -> tuple[str, list[str], list[str], bool, str]:
    """
    Given validator evaluation state, return gate_decision, blocked_reasons, warnings,
    human_approval_required, human_approval_reason.
    """
    warnings = list(validator_warnings or list(evaluation.get("warnings") or []))
    blocked: list[str] = []
    dims = evaluation.get("safety_dimensions") or {}
    primary = str(evaluation.get("primary_risk_level") or "LEVEL_1")

    for dim, state in PROHIBITED_AUTOMATIC_PASS:
        if dims.get(dim) == state:
            blocked.append(f"prohibited_side_effect:{dim}={state}")

    for row in evaluation.get("relevant_unknowns") or []:
        if not isinstance(row, dict):
            continue
        if row.get("relevant_to_plan") and not row.get("safety_verifiable"):
            blocked.append(
                f"relevant_unknown:{row.get('dimension')}:{row.get('observation')}"
            )
        elif not row.get("relevant_to_plan") and row.get("observation"):
            warnings.append(
                f"irrelevant_unknown:{row.get('dimension')}:{row.get('observation')}"
            )

    for dim, state in dims.items():
        if state == "UNKNOWN":
            relevant = dim in ("llm", "gpu", "network", "subprocess", "tool_execution")
            if primary == "LEVEL_1" and dim in ("llm", "gpu", "network"):
                relevant = False
            if relevant:
                blocked.append(f"relevant_unknown:{dim}:dimension_state=UNKNOWN")

    human, human_reason = _human_approval_flags(evaluation)
    if human and (
        dims.get("external_service") == "PRESENT"
        or dims.get("credentials") == "PRESENT"
        or dims.get("network") == "PRESENT"
    ):
        blocked.append(f"human_approval_required:{human_reason or 'policy'}")

    if primary == "LEVEL_3" and not blocked:
        if dims.get("llm") == "PRESENT" or dims.get("gpu") == "PRESENT":
            blocked.append("LEVEL_3_live_resource_without_verified_control")

    decision = "BLOCKED" if blocked else "PASS"
    return decision, blocked, warnings, human, human_reason


def _verify_evaluation_packet(packet: dict[str, Any], schema_path: Path | None) -> str | None:
    if not packet:
        return INVALID_GATE_REASON
    if packet.get("packet_type") != "TEST_SAFETY_EVALUATION":
        return INVALID_GATE_REASON
    if str(packet.get("schema_version")) not in SUPPORTED_EVALUATION_SCHEMA_VERSIONS:
        return INVALID_GATE_REASON
    if schema_path is not None and schema_path.is_file():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(packet)
        except Exception:
            return INVALID_GATE_REASON
    evaluation = packet.get("evaluation")
    if not isinstance(evaluation, dict):
        return INVALID_GATE_REASON
    if "primary_risk_level" not in evaluation or "safety_dimensions" not in evaluation:
        return INVALID_GATE_REASON
    return None


def evaluate_shadow_gate(
    evaluation_packet: dict[str, Any] | None,
    *,
    schema_path: Path | None = None,
    reference_case_id: str | None = None,
) -> dict[str, Any]:
    """Build TEST_SAFETY_SHADOW_GATE packet (shadow only; does not stop execution)."""
    invalid = _verify_evaluation_packet(evaluation_packet or {}, schema_path)
    ref_id = reference_case_id or (evaluation_packet or {}).get("reference_case_id")

    if invalid:
        return {
            "schema_version": "1",
            "packet_type": "TEST_SAFETY_SHADOW_GATE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "gate_id": GATE_ID,
            "shadow_mode": True,
            "execution_authoritative": False,
            "gate_decision": "BLOCKED",
            "warnings": [],
            "blocked_reasons": [invalid],
            "human_approval_required": False,
            "gate_reason": invalid,
            "required_postflight": {"postflight_git_check_required": False},
            "evaluation_ref": {
                "schema_version": str((evaluation_packet or {}).get("schema_version") or ""),
                "packet_type": str((evaluation_packet or {}).get("packet_type") or ""),
                "validator_id": str((evaluation_packet or {}).get("validator_id") or ""),
            },
            **({"reference_case_id": ref_id} if ref_id else {}),
        }

    evaluation = evaluation_packet["evaluation"]
    decision, blocked, warnings, human, human_reason = decide_gate_from_evaluation(evaluation)
    postflight = _postflight_required(evaluation)

    out: dict[str, Any] = {
        "schema_version": "1",
        "packet_type": "TEST_SAFETY_SHADOW_GATE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_id": GATE_ID,
        "shadow_mode": True,
        "execution_authoritative": False,
        "gate_decision": decision,
        "warnings": warnings,
        "blocked_reasons": blocked,
        "human_approval_required": human,
        "required_postflight": {"postflight_git_check_required": postflight},
        "evaluation_ref": {
            "schema_version": evaluation_packet["schema_version"],
            "packet_type": evaluation_packet["packet_type"],
            "validator_id": evaluation_packet["validator_id"],
            "generated_at": evaluation_packet.get("generated_at", ""),
            **(
                {"reference_case_id": evaluation_packet["reference_case_id"]}
                if evaluation_packet.get("reference_case_id")
                else {}
            ),
        },
    }
    if human_reason:
        out["human_approval_reason"] = human_reason
    if ref_id:
        out["reference_case_id"] = ref_id
    return out


def validate_shadow_gate_schema(packet: dict[str, Any], schema_path: Path) -> None:
    import jsonschema

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(packet)
