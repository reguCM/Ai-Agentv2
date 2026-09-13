from __future__ import annotations

from pathlib import Path

import pytest

from validator.validate import validate_tool_spec_file


@pytest.mark.parametrize(
    "spec_path",
    [
        Path("specs/local_get_gpu_status.json"),
        Path("specs/local_cpu_status.json"),
        Path("specs/local_workspace_read_text_scoped.json"),
        Path("specs/local_read_url_text.json"),
    ],
)
def test_valid_specifications_accept(tool_creation_root: Path, spec_path: Path) -> None:
    full = tool_creation_root / spec_path
    result = validate_tool_spec_file(full)
    assert result.verdict == "ACCEPT", result.to_dict()
    assert result.tool_id is not None
    assert result.schema_errors == []
    assert not any(i.get("severity") == "error" for i in result.safety_issues)


def test_gpu_status_required_fields(gpu_status_spec: dict) -> None:
    spec = gpu_status_spec
    for key in (
        "tool_id",
        "name",
        "version",
        "description",
        "provider",
        "source",
        "input_schema",
        "output_schema",
        "side_effect",
        "risk_level",
        "cost",
    ):
        assert key in spec, f"missing {key}"
    assert spec["provider"] == "local"
    assert spec["side_effect"] == "read_only"
    assert spec["risk_level"] == "low"
    contract = spec["contract"]
    for block in ("can", "cannot", "must", "must_not"):
        assert isinstance(contract.get(block), list) and contract[block]


def test_cpu_status_input_output_schema(cpu_status_spec: dict) -> None:
    spec = cpu_status_spec
    assert spec["input_schema"]["type"] == "object"
    assert "status" in spec["output_schema"]["properties"]
