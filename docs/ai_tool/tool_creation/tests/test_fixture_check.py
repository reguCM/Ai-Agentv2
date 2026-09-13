from __future__ import annotations

from pathlib import Path

import pytest

from validator.output_check import check_output_schema_against_fixture
from validator.validate import validate_tool_spec_file

# NOT READY: live tool execution vs fixture — Phase 3-1 uses static fixture only.


@pytest.mark.fixture_check
def test_fc06_output_fixture_mismatch_detected(tool_creation_root: Path) -> None:
    path = tool_creation_root / "failure_cases" / "fc06_output_schema_mismatch.json"
    result = validate_tool_spec_file(path)
    assert result.verdict == "REJECT"
    codes = [i.get("code") for i in result.safety_issues]
    assert "OUTPUT_SCHEMA_MISMATCH" in codes


@pytest.mark.fixture_check
def test_gpu_fixture_exists(tool_creation_root: Path) -> None:
    fixture = tool_creation_root / "fixtures" / "get_gpu_status_sample_keys.json"
    assert fixture.is_file()
    keys = __import__("json").loads(fixture.read_text(encoding="utf-8")).get("sample_keys")
    assert "gpu" in keys
    assert "observation_source" in keys


@pytest.mark.fixture_check
def test_valid_gpu_spec_passes_fixture_check(gpu_status_spec: dict, tool_creation_root: Path) -> None:
    issues = check_output_schema_against_fixture(
        gpu_status_spec, base_dir=tool_creation_root
    )
    errors = [i for i in issues if i.get("severity") == "error"]
    assert errors == []
