"""Deterministic Agent bridge tests for get_gpu_processes E2E (Phase 2)."""
from __future__ import annotations

import json

import pytest

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    production_schema_snapshot,
    run_e2e_scenario,
    verify_agent_integration_state,
)
from ai_tool.agent_integration.gpu_process_e2e_scenarios import (
    DET_CASE1_GPU_PROCESSES,
    DET_CASE2_GPU_VRAM,
    DET_CASE3_CPU_NOT_GPU_PROC,
    DET_CASE4_GPU_STATUS,
    DET_CASE5_CPU_STRUCTURED,
    DETERMINISTIC_SCENARIOS,
)


@pytest.fixture(scope="module")
def agent_tools():
    return build_production_agent_tools()


@pytest.fixture(scope="module")
def schema_before():
    return production_schema_snapshot()


def test_phase1_get_gpu_processes_in_registry_and_schema(agent_tools: list) -> None:
    state = verify_agent_integration_state()
    assert state.discovered is True
    assert state.selectable is True
    assert state.get_gpu_processes_exposed is True
    assert state.get_gpu_processes_experimental is False
    names = {t["function"]["name"] for t in agent_tools}
    assert "get_gpu_processes" in names


@pytest.mark.parametrize("scenario", DETERMINISTIC_SCENARIOS, ids=lambda s: s.scenario_id)
def test_deterministic_routing_and_execution(scenario, agent_tools: list) -> None:
    result = run_e2e_scenario(scenario, tools=agent_tools)
    assert result.routing_match is True, result.to_dict()
    assert result.executed is True
    assert result.result_returned is True
    assert result.selected_tools[0] == scenario.expected_tool


def test_get_gpu_processes_result_structure_mock(agent_tools: list) -> None:
    from unittest import mock

    with mock.patch(
        "tools.system.gpu.nvidia_smi.nvidia_smi_path",
        return_value="nvidia-smi",
    ), mock.patch(
        "tools.system.gpu.nvidia_smi._run_nvidia_smi_query",
        return_value={
            "ok": True,
            "error": None,
            "status": "ok",
            "rows": [["111", "chrome.exe", "[N/A]"]],
            "source": "nvidia-smi",
        },
    ):
        rec = execute_registry_tool("get_gpu_processes", {})
    result = rec.result
    assert isinstance(result, dict)
    assert "processes" in result
    assert result["observation_source"] == "real"
    assert result["processes"][0]["vram_used"] == "unknown"
    assert result["processes"][0]["vram_used"] != 0


def test_regression_production_schema_unchanged(schema_before: dict) -> None:
    after = production_schema_snapshot()
    assert after == schema_before


def test_case1_messages_include_tool_result(agent_tools: list) -> None:
    result = run_e2e_scenario(DET_CASE1_GPU_PROCESSES, tools=agent_tools)
    exec0 = result.executions[0]
    payload = exec0["result"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert "processes" in payload


def test_observation_real_partial_semantics_direct() -> None:
    """REAL: pid/name/list — PARTIAL: per-process VRAM; unknown must not become 0."""
    rec = execute_registry_tool("get_gpu_processes", {})
    result = rec.result
    if not isinstance(result, dict) or not result.get("ok"):
        pytest.skip("nvidia-smi unavailable in this environment")
    processes = result.get("processes") or []
    assert isinstance(processes, list)
    assert result.get("observation_source") == "real"
    for proc in processes:
        assert isinstance(proc.get("pid"), int)
        assert isinstance(proc.get("name"), str)
        vram = proc.get("vram_used")
        assert vram == "unknown" or isinstance(vram, int)
        if vram == "unknown":
            assert vram != 0


def test_independent_observation_passes_with_vram_unknown() -> None:
    """VRAM unknown is recorded, not treated as test failure."""
    from ai_tool.agent_integration.gpu_process_e2e import compare_with_nvidia_smi

    rec = execute_registry_tool("get_gpu_processes", {})
    result = rec.result if isinstance(rec.result, dict) else {}
    if not result.get("ok"):
        pytest.skip("nvidia-smi unavailable in this environment")
    comparison = compare_with_nvidia_smi(result)
    assert comparison.get("overall") in ("PASS", "PARTIAL")
    assert comparison.get("pid_match_rate", 0) >= 0.8
    unknown_count = comparison.get("tool_vram_unknown_count", 0)
    if unknown_count:
        assert comparison.get("overall") != "FAIL"
