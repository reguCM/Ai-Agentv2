"""Context Monitor ユニットテスト。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.system.context_monitor.aggregate import aggregate_observations
from tools.system.context_monitor.import_legacy import observations_from_verify
from tools.system.context_monitor.recalibration import evaluate_recalibration
from tools.system.context_monitor.record import (
    append_observation,
    build_observation,
    is_monitor_enabled,
    load_observations,
)


@pytest.fixture
def obs_path(tmp_path, monkeypatch):
    path = tmp_path / "observations.jsonl"
    monkeypatch.setattr(
        "tools.system.context_monitor.record.OBSERVATIONS_JSONL",
        path,
    )
    monkeypatch.setattr(
        "tools.system.context_monitor.paths.OBSERVATIONS_JSONL",
        path,
    )
    return path


def test_build_and_append_observation(obs_path):
    obs = build_observation(
        source="test",
        model="qwen3:14b",
        profile_id="qwen3_14b",
        context_size=16384,
        tools_enabled=True,
        task_type="search_read",
        gpu_before={"vram_free_mib": 500},
        gpu_after={"vram_free_mib": 300},
        outcome={"success": True, "timeout": False, "native_tool_call": True},
        performance={"elapsed_ms": 25000},
    )
    obs_id = append_observation(obs, path=obs_path)
    rows = load_observations(path=obs_path)
    assert len(rows) == 1
    assert rows[0]["observation_id"] == obs_id
    assert rows[0]["execution"]["context_size"] == 16384
    assert "evaluation" not in rows[0]


def test_aggregate_by_context(obs_path):
    for ctx, success, timeout, elapsed, vram in [
        (8192, True, False, 30000, 800),
        (8192, False, True, 90000, 400),
        (16384, True, False, 25000, 500),
    ]:
        append_observation(
            build_observation(
                source="test",
                model="m",
                profile_id="p",
                context_size=ctx,
                tools_enabled=True,
                outcome={"success": success, "timeout": timeout},
                performance={"elapsed_ms": elapsed},
                gpu_before={"vram_free_mib": vram},
            ),
            path=obs_path,
        )
    summary = aggregate_observations(load_observations(path=obs_path))
    assert summary["total_observations"] == 3
    assert summary["evaluation_state"] == "insufficient_data"
    assert "8192" in summary["by_context_size"]
    assert summary["by_context_size"]["8192"]["observation_count"] == 2
    assert summary["by_context_size"]["8192"]["timeout_rate"] == 0.5


def test_recalibration_insufficient_data(obs_path):
    append_observation(
        build_observation(
            source="test",
            model="m",
            profile_id="p",
            context_size=16384,
            tools_enabled=True,
            outcome={"success": False, "timeout": True},
            performance={"elapsed_ms": 90000},
            gpu_before={"vram_free_mib": 200},
        ),
        path=obs_path,
    )
    summary = aggregate_observations(load_observations(path=obs_path))
    status = evaluate_recalibration(summary, focus_context=16384)
    assert status["status"] == "none"
    assert status["recalibration_required"] is False


def test_import_p26_structure():
    verify = {
        "timestamp": "20260902T070613Z",
        "llm_profile": {"model": "qwen3:14b", "id": "qwen3_14b", "context_limit": 8192},
        "runs": [
            {
                "run_number": 1,
                "native_read_file_generated": False,
                "read_file_executed": False,
                "read_file_after_search": False,
                "type3_fabrication_suspected": True,
                "tool_sequence": ["search_files"],
            },
            {
                "run_number": 2,
                "native_read_file_generated": True,
                "read_file_executed": True,
                "read_file_after_search": True,
                "type3_fabrication_suspected": False,
                "tool_sequence": ["search_files", "read_file"],
            },
        ],
    }
    rows = observations_from_verify(
        verify,
        phase="P2-6",
        verify_path=Path(__file__).resolve().parents[1] / "runs" / "x" / "verify.json",
        context_size=8192,
    )
    assert len(rows) == 2
    assert rows[0]["outcome"]["type3"] is True
    assert rows[1]["outcome"]["success"] is True


def test_is_monitor_env(monkeypatch):
    monkeypatch.delenv("AI_AGENT_CONTEXT_MONITOR", raising=False)
    assert is_monitor_enabled() is True
    monkeypatch.setenv("AI_AGENT_CONTEXT_MONITOR", "0")
    assert is_monitor_enabled() is False
