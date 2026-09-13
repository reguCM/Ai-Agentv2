"""get_memory_status — 契約と CIM 実測。"""
from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from unittest import mock

from tools.system.memory.get_memory_status import UNKNOWN, get_memory_status

REQUIRED = ("total_mb", "used_mb", "free_mb", "used_percent")


def test_direct_call_returns_real_memory_on_windows():
    if platform.system().lower() != "windows":
        out = get_memory_status()
        assert out["ok"] is False
        assert out["status"] == "unavailable"
        return
    out = get_memory_status()
    assert out["ok"] is True
    assert out["status"] == "ok"
    assert out["error"] is None
    for key in REQUIRED:
        assert isinstance(out[key], int)
    assert out["total_mb"] > 0
    assert out["free_mb"] >= 0
    assert out["used_mb"] >= 0
    assert 0 <= out["used_percent"] <= 100
    assert out["used_mb"] + out["free_mb"] <= out["total_mb"] + 1


def test_return_shape():
    out = get_memory_status()
    for key in REQUIRED:
        assert key in out
    assert out["observation_source"] == "real"
    assert out["source"] == "win32_operating_system_cim"
    assert "ok" in out
    assert "status" in out
    assert "error" in out


def test_mocked_cim_success():
    payload = {"TotalVisibleMemorySize": 16 * 1024 * 1024, "FreePhysicalMemory": 4 * 1024 * 1024}
    with mock.patch("platform.system", return_value="Windows"), mock.patch(
        "tools.system.memory.get_memory_status.subprocess.run",
        return_value=mock.Mock(returncode=0, stdout=json.dumps(payload), stderr=""),
    ):
        out = get_memory_status()
    assert out["ok"] is True
    assert out["total_mb"] == 16 * 1024
    assert out["free_mb"] == 4 * 1024
    assert out["used_mb"] == 12 * 1024
    assert out["used_percent"] == 75


def test_non_windows_unavailable():
    with mock.patch("platform.system", return_value="Linux"):
        out = get_memory_status()
    assert out["ok"] is False
    assert out["status"] == "unavailable"
    assert out["total_mb"] == UNKNOWN


def test_cim_failure_unknown_fields():
    with mock.patch("platform.system", return_value="Windows"), mock.patch(
        "tools.system.memory.get_memory_status.subprocess.run",
        return_value=mock.Mock(returncode=1, stdout="", stderr="fail"),
    ):
        out = get_memory_status()
    assert out["ok"] is False
    assert out["total_mb"] == UNKNOWN
    assert out["used_percent"] == UNKNOWN


def test_registry_entry_matches_observation_tools():
    registry = json.loads(
        (Path(__file__).resolve().parents[1] / "registry" / "tools.json").read_text(encoding="utf-8")
    )
    entry = next(t for t in registry["tools"] if t["name"] == "get_memory_status")
    assert entry["visibility"] == "agent"
    assert entry["observation_source"] == "real"
    assert entry["module"] == "tools.system.memory.get_memory_status"
    assert entry["function"] == "get_memory_status"
    assert entry["input"] == {}
    names = [t["name"] for t in registry["tools"]]
    assert names.count("get_memory_status") == 1
    assert "get_cpu_status" in names
    assert "get_system_time" in names


def test_does_not_alter_existing_cpu_or_time_modules():
    cpu = Path("tools/system/cpu/get_cpu_status.py").read_text(encoding="utf-8")
    time_src = Path("tools/system/time/get_system_time.py").read_text(encoding="utf-8")
    assert "get_memory_status" not in cpu
    assert "get_memory_status" not in time_src


def test_existing_observation_tools_still_run():
    from tools.system.cpu.get_cpu_status import get_cpu_status
    from tools.system.gpu.gpu_status import get_gpu_status
    from tools.system.time.get_system_time import get_system_time

    time_out = get_system_time()
    assert time_out["ok"] is True
    cpu_out = get_cpu_status()
    assert cpu_out["observation_source"] == "real"
    gpu_out = get_gpu_status()
    assert gpu_out["observation_source"] == "real"
