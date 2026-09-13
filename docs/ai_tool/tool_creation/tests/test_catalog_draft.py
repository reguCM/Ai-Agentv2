from __future__ import annotations

from validator.catalog_draft import generate_catalog_draft


def test_catalog_draft_from_gpu_status(gpu_status_spec: dict) -> None:
    draft = generate_catalog_draft(gpu_status_spec, spec_ref="specs/local_get_gpu_status.json")
    assert draft["tool_id"] == "local:get_gpu_status"
    assert draft["provider"] == "local"
    assert draft["input_schema"] == gpu_status_spec["input_schema"]
    assert draft["output_schema"] == gpu_status_spec["output_schema"]
    assert draft["side_effect"] == "read_only"
    assert draft["permissions"] == ["visibility:agent"]
    assert draft["risk_level"] == "low"
    assert draft["cost"] == "free"
    assert draft["tool_status"] == "available"
    assert draft["experiment_status"] == "tested"
    assert draft["adoption_status"] == "approved"
    assert draft["_draft_meta"]["registry_modified"] is False


def test_catalog_draft_from_cpu_status(cpu_status_spec: dict) -> None:
    draft = generate_catalog_draft(cpu_status_spec)
    assert draft["tool_id"] == "local:cpu_status"
    assert draft["experiment_status"] == "unknown"
    assert draft["adoption_status"] == "approved"
    assert "experiment_status" not in draft["_draft_meta"]["inferred_fields"]


def test_catalog_draft_does_not_modify_registry(gpu_status_spec: dict) -> None:
    draft = generate_catalog_draft(gpu_status_spec)
    assert draft["_draft_meta"]["registry_modified"] is False
