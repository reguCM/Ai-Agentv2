from __future__ import annotations

from validator.catalog_draft import generate_catalog_draft
from validator.validate import validate_tool_spec


MINIMAL_SPEC = {
    "tool_id": "local:minimal_unknown",
    "name": "minimal_unknown",
    "version": "1.0.0",
    "description": "spec without catalog_hints or required_permission",
    "provider": "local",
    "source": "test",
    "capability": ["test"],
    "purpose": "unknown policy test",
    "allowed_operations": ["read"],
    "prohibited_operations": [],
    "input_schema": {"type": "object", "additionalProperties": False},
    "output_schema": {"type": "object"},
    "error_format": {},
    "side_effect": "read_only",
    "authentication": "none",
    "network_access": False,
    "filesystem_access": "none",
    "risk_level": "low",
    "cost": "free",
    "tool_status": "available",
    "contract": {
        "can": ["read"],
        "cannot": ["write"],
        "must": ["return_dict"],
        "must_not": ["fabricate"],
    },
}


def test_missing_catalog_hints_become_unknown() -> None:
    draft = generate_catalog_draft(MINIMAL_SPEC)
    assert draft["experiment_status"] == "UNKNOWN"
    assert draft["adoption_status"] == "UNKNOWN"
    assert "experiment_status" in draft["_draft_meta"]["inferred_fields"]
    assert "adoption_status" in draft["_draft_meta"]["inferred_fields"]


def test_missing_required_permission_becomes_unknown() -> None:
    draft = generate_catalog_draft(MINIMAL_SPEC)
    assert draft["permissions"] == ["UNKNOWN"]


def test_invalid_catalog_hints_reject_not_coerce() -> None:
    bad = dict(MINIMAL_SPEC)
    bad["catalog_hints"] = {
        "experiment_status": "auto_approved",
        "adoption_status": "production_ready",
    }
    result = validate_tool_spec(bad)
    assert result.verdict == "REJECT"
    draft = generate_catalog_draft(bad)
    assert draft["experiment_status"] == "UNKNOWN"
    assert draft["adoption_status"] == "UNKNOWN"


def test_no_fabricated_provider_specific_fields() -> None:
    draft = generate_catalog_draft(MINIMAL_SPEC)
    assert draft["provider_specific"] == {}


def test_no_fabricated_cost_or_risk_when_present_in_spec() -> None:
    draft = generate_catalog_draft(MINIMAL_SPEC)
    assert draft["cost"] == "free"
    assert draft["risk_level"] == "low"
    # Values come from spec keys, not invented defaults beyond spec content
