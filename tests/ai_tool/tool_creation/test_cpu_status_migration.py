"""Contract tests for cpu_status legacy migration Phase 2 (implementation UNCHANGED)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOL_CREATION = REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

SPEC_PATH = TOOL_CREATION / "specs" / "cpu_status_legacy_migrated.json"
REQUIRED_KEYS = ("status",)


@pytest.fixture(scope="module")
def migrated_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry_entry() -> dict:
    reg = json.loads((REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    return next(t for t in reg["tools"] if t["name"] == "cpu_status")


def test_migrated_spec_validates_accept() -> None:
    from validator.validate import validate_tool_spec_file

    result = validate_tool_spec_file(SPEC_PATH)
    assert result.verdict == "ACCEPT", result.to_dict()


def test_output_keys_match_spec(migrated_spec: dict) -> None:
    spec_keys = set(migrated_spec["output_schema"]["properties"].keys())
    assert spec_keys == set(REQUIRED_KEYS)
    assert migrated_spec["output_schema"]["required"] == ["status"]


def test_success_output_contract_mock() -> None:
    from tools.system.cpu.cpu_status import cpu_status

    fake_stdout = "LoadPercentage\n-----\n42\n"
    with mock.patch(
        "tools.system.cpu.cpu_status.subprocess.run",
        return_value=mock.Mock(returncode=0, stdout=fake_stdout, stderr=""),
    ):
        out = cpu_status()
    assert set(out.keys()) == set(REQUIRED_KEYS)
    assert out["status"] == "42"


def test_failure_returns_status_error() -> None:
    from tools.system.cpu.cpu_status import cpu_status

    with mock.patch(
        "tools.system.cpu.cpu_status.subprocess.run",
        return_value=mock.Mock(returncode=1, stdout="", stderr="fail"),
    ):
        out = cpu_status()
    assert out == {"status": "error"}


def test_no_hardcoded_success_load() -> None:
    from tools.system.cpu.cpu_status import cpu_status

    with mock.patch(
        "tools.system.cpu.cpu_status.subprocess.run",
        return_value=mock.Mock(returncode=1, stdout="", stderr=""),
    ):
        out = cpu_status()
    assert out["status"] == "error"
    assert out["status"] != "28"


def test_registry_partial_match(registry_entry: dict, migrated_spec: dict) -> None:
    ps = migrated_spec["provider_specific"]
    assert registry_entry["name"] == migrated_spec["name"]
    assert registry_entry["module"] == ps["module"]
    assert registry_entry["function"] == ps["function"]
    assert registry_entry.get("observation_source") == "real"
    assert registry_entry.get("visibility") == "agent"
    assert registry_entry.get("input") == {}
    assert registry_entry.get("output") == ["status"]


def test_observation_source_not_in_output(migrated_spec: dict) -> None:
    assert "observation_source" not in migrated_spec["output_schema"]["properties"]
    assert migrated_spec["not_provided_fields"]["observation_source"]["status"] == "NOT_PROVIDED"


def test_compatibility_no_output_key_change(migrated_spec: dict) -> None:
    must_not = " ".join(migrated_spec["contract"]["must_not"])
    assert "add_output_keys_without_human_review" in must_not


def test_not_provided_fields_documented(migrated_spec: dict) -> None:
    for field in ("model", "cores", "threads", "temperature"):
        assert migrated_spec["not_provided_fields"][field]["status"] == "NOT_PROVIDED"


@pytest.mark.real_cpu
def test_live_observation_optional() -> None:
    """Local live observation — skip outside Windows/PowerShell."""
    import platform
    import shutil

    if platform.system() != "Windows" or shutil.which("powershell") is None:
        pytest.skip("Windows PowerShell required")
    from tools.system.cpu.cpu_status import cpu_status

    out = cpu_status()
    assert set(out.keys()) == set(REQUIRED_KEYS)
    if out["status"] != "error":
        assert out["status"].isdigit() or out["status"].replace(".", "", 1).isdigit()
