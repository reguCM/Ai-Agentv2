"""Contract tests for get_gpu_status legacy migration (Phase 1 — implementation UNCHANGED)."""
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

SPEC_PATH = TOOL_CREATION / "specs" / "get_gpu_status_legacy_migrated.json"
FIXTURE_KEYS = TOOL_CREATION / "fixtures" / "get_gpu_status_sample_keys.json"
REQUIRED_KEYS = (
    "gpu",
    "temperature",
    "utilization",
    "vram_used",
    "vram_total",
    "ok",
    "status",
    "error",
    "observation_source",
    "source",
)


@pytest.fixture(scope="module")
def migrated_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry_entry() -> dict:
    reg = json.loads((REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    return next(t for t in reg["tools"] if t["name"] == "get_gpu_status")


def test_migrated_spec_validates_accept() -> None:
    from validator.validate import validate_tool_spec_file

    result = validate_tool_spec_file(SPEC_PATH)
    assert result.verdict == "ACCEPT", result.to_dict()


def test_output_keys_match_fixture_and_spec(migrated_spec: dict) -> None:
    fixture = json.loads(FIXTURE_KEYS.read_text(encoding="utf-8"))
    spec_keys = set(migrated_spec["output_schema"]["properties"].keys())
    fixture_keys = set(fixture["sample_keys"])
    assert spec_keys == fixture_keys == set(REQUIRED_KEYS)


def test_success_output_contract_mock() -> None:
    from tools.system.gpu.gpu_status import get_gpu_status

    with mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [["GeForce TEST", "41", "7", "1234", "8192"]],
            "source": "nvidia-smi",
        },
    ), mock.patch("tools.system.gpu.nvidia_smi.nvidia_smi_path", return_value="nvidia-smi"):
        out = get_gpu_status()
    assert set(out.keys()) == set(REQUIRED_KEYS)
    assert out["ok"] is True
    assert out["observation_source"] == "real"
    assert out["gpu"] == "GeForce TEST"
    assert out["temperature"] == 41.0
    assert out["utilization"] == 7.0
    assert out["vram_used"] == 1234
    assert out["vram_total"] == 8192


def test_failure_no_hardcoded_fallback() -> None:
    from tools.system.gpu.gpu_status import get_gpu_status

    with mock.patch("tools.system.gpu.nvidia_smi.nvidia_smi_path", return_value=None):
        out = get_gpu_status()
    assert out["ok"] is False
    assert out["gpu"] == "unknown"
    assert out["temperature"] == "unknown"
    assert out["observation_source"] == "real"
    assert out["gpu"] != "RTX 3060"


def test_registry_partial_match(registry_entry: dict, migrated_spec: dict) -> None:
    ps = migrated_spec["provider_specific"]
    assert registry_entry["name"] == migrated_spec["name"]
    assert registry_entry["module"] == ps["module"]
    assert registry_entry["function"] == ps["function"]
    assert registry_entry.get("observation_source") == "real"
    assert registry_entry.get("visibility") == "agent"
    assert registry_entry.get("input") == {}


def test_agent_path_unchanged_registry_has_agent_visibility(registry_entry: dict) -> None:
    assert registry_entry.get("visibility") == "agent"


def test_compatibility_no_output_key_change(migrated_spec: dict) -> None:
    must_not = migrated_spec["contract"]["must_not"]
    assert "remove_existing_output_keys" in " ".join(must_not)
    assert "change_output_key_meanings" in " ".join(must_not)


@pytest.mark.real_gpu
def test_live_observation_optional() -> None:
    """Local live observation — skip in CI without GPU."""
    import shutil

    if shutil.which("nvidia-smi") is None:
        pytest.skip("nvidia-smi not available")
    from tools.system.gpu.gpu_status import get_gpu_status

    out = get_gpu_status()
    assert set(out.keys()) == set(REQUIRED_KEYS)
    if out["ok"]:
        assert isinstance(out["gpu"], str)
        assert out["observation_source"] == "real"
