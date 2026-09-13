"""Capability audit tests — probe logic and existing behavior (no production changes)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.run_observation_capability_audit import (
    compare_gpu_status,
    head_gpu_status_stub,
    probe_cpu,
    probe_gpu,
    tool_outputs_wt,
)


def test_head_gpu_status_is_fixed_stub():
    stub = head_gpu_status_stub()
    assert stub["classification"] == "FIXED_STUB"
    assert stub["gpu"] == "RTX 3060"
    assert "observation_source" not in stub


def test_compare_gpu_status_model_real():
    rows = compare_gpu_status(
        {"gpu": "NVIDIA GeForce RTX 3060", "temperature": 57.0, "utilization": 18.0, "vram_used": 1868, "vram_total": 12288},
        "NVIDIA GeForce RTX 3060, 57, 18, 1868, 12288, 1",
    )
    by_field = {r["field"]: r for r in rows}
    assert by_field["gpu"]["verdict"] == "REAL"
    assert by_field["gpu_count"]["verdict"] == "NOT_PROVIDED"


def test_tool_outputs_wt_get_gpu_processes_vram_not_zero():
    out = tool_outputs_wt()
    gp = out["get_gpu_processes"]
    if gp.get("process_count", 0) == 0:
        pytest.skip("no gpu processes in environment")
    assert gp["vram_unknown_count"] >= 0
    # If unknown present, must not be coerced to 0 in sample paths
    sample = out["get_gpu_processes"].get("sample") or []
    for proc in sample:
        assert proc.get("vram_used") != 0


def test_probe_gpu_structure():
    probe = probe_gpu()
    assert "nvidia_smi_available" in probe


def test_probe_cpu_load_available_on_windows():
    probe = probe_cpu()
    load = probe.get("load") or {}
    if load.get("error"):
        pytest.skip("powershell unavailable")
    assert load.get("returncode") == 0
    assert "LoadPercentage" in (load.get("stdout") or "")


def test_audit_script_runs():
    proc = subprocess.run(
        [sys.executable, "ai_tool/run_observation_capability_audit.py"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    run_dir = Path(payload["run_dir"])
    assert (run_dir / "REPORT.json").exists()
    assert (run_dir / "evaluation.json").exists()
