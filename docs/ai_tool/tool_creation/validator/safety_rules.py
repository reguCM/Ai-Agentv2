from __future__ import annotations

from typing import Any


def check_structural_safety(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Structural safety checks beyond JSON Schema. Does not execute tools."""
    issues: list[dict[str, str]] = []

    side_effect = spec.get("side_effect")
    network_access = spec.get("network_access")
    filesystem_access = spec.get("filesystem_access")
    allowed = set(spec.get("allowed_operations") or [])
    prohibited = set(spec.get("prohibited_operations") or [])
    risk = spec.get("risk_level")

    if side_effect == "none" and network_access is True:
        issues.append(
            {
                "code": "SIDE_EFFECT_NETWORK_CONFLICT",
                "severity": "error",
                "message": "side_effect is none but network_access is true",
            }
        )
    if side_effect == "read_only" and network_access is True and "network" not in allowed:
        issues.append(
            {
                "code": "SIDE_EFFECT_NETWORK_CONFLICT",
                "severity": "error",
                "message": (
                    "read_only with network_access requires 'network' in allowed_operations"
                ),
            }
        )

    if side_effect in ("none", "read_only") and filesystem_access in ("write", "read_write"):
        issues.append(
            {
                "code": "SIDE_EFFECT_FILESYSTEM_CONFLICT",
                "severity": "error",
                "message": "side_effect is read-only/none but filesystem_access allows write",
            }
        )

    if "write" in allowed and "write" in prohibited:
        issues.append(
            {
                "code": "OPERATION_CONTRADICTION",
                "severity": "error",
                "message": "write appears in both allowed_operations and prohibited_operations",
            }
        )

    if "modify" in allowed and "modify" in prohibited:
        issues.append(
            {
                "code": "OPERATION_CONTRADICTION",
                "severity": "error",
                "message": "modify appears in both allowed_operations and prohibited_operations",
            }
        )

    if side_effect in ("write", "modify") and risk == "low":
        issues.append(
            {
                "code": "RISK_SIDE_EFFECT_MISMATCH",
                "severity": "warning",
                "message": "write/modify side_effect with risk_level low — review required",
            }
        )

    contract = spec.get("contract")
    if not isinstance(contract, dict):
        issues.append(
            {
                "code": "CONTRACT_MISSING",
                "severity": "error",
                "message": "contract block is required for structural validation",
            }
        )
    else:
        for key in ("can", "cannot", "must", "must_not"):
            value = contract.get(key)
            if not isinstance(value, list) or not value:
                issues.append(
                    {
                        "code": "CONTRACT_INCOMPLETE",
                        "severity": "error",
                        "message": f"contract.{key} must be a non-empty list",
                    }
                )

    input_schema = spec.get("input_schema")
    if not isinstance(input_schema, dict):
        issues.append(
            {
                "code": "INPUT_SCHEMA_INVALID",
                "severity": "error",
                "message": "input_schema must be an object",
            }
        )
    elif input_schema.get("type") != "object":
        issues.append(
            {
                "code": "INPUT_SCHEMA_TYPE",
                "severity": "error",
                "message": "input_schema.type should be 'object'",
            }
        )

    output_schema = spec.get("output_schema")
    if output_schema is None:
        issues.append(
            {
                "code": "OUTPUT_SCHEMA_MISSING",
                "severity": "error",
                "message": "output_schema is required for structural validation",
            }
        )

    hints = spec.get("catalog_hints")
    if isinstance(hints, dict):
        exp_allowed = {"unknown", "experimental", "tested", "unsupported"}
        ad_allowed = {"not_reviewed", "candidate", "approved", "rejected"}
        if "experiment_status" in hints and str(hints["experiment_status"]) not in exp_allowed:
            issues.append(
                {
                    "code": "INVALID_CATALOG_HINTS",
                    "severity": "error",
                    "message": (
                        "catalog_hints.experiment_status must be one of "
                        f"{sorted(exp_allowed)}; got {hints['experiment_status']!r}"
                    ),
                }
            )
        if "adoption_status" in hints and str(hints["adoption_status"]) not in ad_allowed:
            issues.append(
                {
                    "code": "INVALID_CATALOG_HINTS",
                    "severity": "error",
                    "message": (
                        "catalog_hints.adoption_status must be one of "
                        f"{sorted(ad_allowed)}; got {hints['adoption_status']!r}"
                    ),
                }
            )

    return issues
