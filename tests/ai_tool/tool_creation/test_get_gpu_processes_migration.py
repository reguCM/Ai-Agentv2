"""Contract tests for get_gpu_processes legacy migration Phase 1 (implementation UNCHANGED)."""
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

SPEC_PATH = TOOL_CREATION / "specs" / "get_gpu_processes_legacy_migrated.json"
REQUIRED_TOP_KEYS = ("processes", "ok", "status", "error", "observation_source", "source")
PROCESS_KEYS = ("pid", "name", "vram_used")


@pytest.fixture(scope="module")
def migrated_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry_entry() -> dict:
    reg = json.loads((REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    return next(t for t in reg["tools"] if t["name"] == "get_gpu_processes")


def test_migrated_spec_validates_accept() -> None:
    from validator.validate import validate_tool_spec_file

    result = validate_tool_spec_file(SPEC_PATH)
    assert result.verdict == "ACCEPT", result.to_dict()


def test_output_keys_match_spec(migrated_spec: dict) -> None:
    spec_keys = set(migrated_spec["output_schema"]["properties"].keys())
    assert spec_keys == set(REQUIRED_TOP_KEYS)
    assert migrated_spec["output_schema"]["required"] == list(REQUIRED_TOP_KEYS)


def test_success_process_list_structure() -> None:
    from tools.system.gpu.gpu_processes import get_gpu_processes

    with mock.patch(
        "tools.system.gpu.nvidia_smi.nvidia_smi_path",
        return_value="nvidia-smi",
    ), mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [["111", "chrome.exe", "200"], ["222", "python.exe", "512"]],
            "source": "nvidia-smi",
        },
    ):
        out = get_gpu_processes()
    assert set(out.keys()) == set(REQUIRED_TOP_KEYS)
    assert out["ok"] is True
    assert out["observation_source"] == "real"
    assert len(out["processes"]) == 2
    for proc in out["processes"]:
        assert set(proc.keys()) == set(PROCESS_KEYS)
    assert out["processes"][0]["pid"] == 111
    assert out["processes"][0]["name"] == "chrome.exe"
    assert out["processes"][0]["vram_used"] == 200


def test_empty_process_list_success() -> None:
    from tools.system.gpu.gpu_processes import get_gpu_processes

    with mock.patch(
        "tools.system.gpu.nvidia_smi.nvidia_smi_path",
        return_value="nvidia-smi",
    ), mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [],
            "source": "nvidia-smi",
        },
    ):
        out = get_gpu_processes()
    assert out["ok"] is True
    assert out["processes"] == []
    assert out["status"] == "ok"


def test_failure_empty_no_hardcoded_fallback() -> None:
    from tools.system.gpu.gpu_processes import get_gpu_processes

    with mock.patch("tools.system.gpu.nvidia_smi.nvidia_smi_path", return_value=None):
        out = get_gpu_processes()
    assert out["processes"] == []
    assert out["ok"] is False
    assert out["observation_source"] == "real"
    assert out["processes"] != [
        {"name": "ollama", "vram_used": 4500},
        {"name": "python.exe", "vram_used": 1200},
    ]


def test_vram_na_becomes_unknown_not_zero() -> None:
    from tools.system.gpu.gpu_processes import get_gpu_processes

    with mock.patch(
        "tools.system.gpu.nvidia_smi.nvidia_smi_path",
        return_value="nvidia-smi",
    ), mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [["333", "app.exe", "[N/A]"]],
            "source": "nvidia-smi",
        },
    ):
        out = get_gpu_processes()
    assert out["processes"][0]["vram_used"] == "unknown"
    assert out["processes"][0]["vram_used"] != 0


def test_no_hardcoded_ollama_python() -> None:
    from tools.system.gpu.gpu_processes import get_gpu_processes

    with mock.patch(
        "tools.system.gpu.nvidia_smi.nvidia_smi_path",
        return_value="nvidia-smi",
    ), mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [["111", "chrome.exe", "200"]],
            "source": "nvidia-smi",
        },
    ):
        out = get_gpu_processes()
    names = [p["name"] for p in out["processes"]]
    assert names == ["chrome.exe"]
    assert "ollama" not in names


def test_registry_partial_match(registry_entry: dict, migrated_spec: dict) -> None:
    ps = migrated_spec["provider_specific"]
    assert registry_entry["name"] == migrated_spec["name"]
    assert registry_entry["module"] == ps["module"]
    assert registry_entry["function"] == ps["function"]
    assert registry_entry.get("observation_source") == "real"
    assert registry_entry.get("visibility") == "agent"
    assert registry_entry.get("input") == {}


def test_gpu_id_not_provided(migrated_spec: dict) -> None:
    assert migrated_spec["not_provided_fields"]["gpu_id"]["status"] == "NOT_PROVIDED"


def test_compatibility_no_output_key_change(migrated_spec: dict) -> None:
    must_not = " ".join(migrated_spec["contract"]["must_not"])
    assert "remove_existing_output_keys" in must_not


@pytest.mark.real_gpu
def test_live_observation_optional() -> None:
    """Local live observation — skip without nvidia-smi."""
    import shutil

    if shutil.which("nvidia-smi") is None:
        pytest.skip("nvidia-smi not available")
    from tools.system.gpu.gpu_processes import get_gpu_processes

    out = get_gpu_processes()
    assert set(out.keys()) == set(REQUIRED_TOP_KEYS)
    assert isinstance(out["processes"], list)
    assert out["observation_source"] == "real"
