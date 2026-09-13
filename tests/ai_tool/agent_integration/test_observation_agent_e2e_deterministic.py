"""Observation Implementation Phase 1 — Agent E2E deterministic routing."""
from __future__ import annotations

import pytest

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    production_schema_snapshot,
    run_e2e_scenario,
    verify_agent_integration_state,
)
from ai_tool.agent_integration.gpu_process_e2e_scenarios import (
    DET_CASE4_GPU_STATUS,
    DET_CASE5_CPU_STRUCTURED,
    DETERMINISTIC_SCENARIOS,
)


@pytest.fixture(scope="module")
def agent_tools():
    return build_production_agent_tools()


def test_observation_tools_exposed(agent_tools: list) -> None:
    names = {t["function"]["name"] for t in agent_tools}
    required = {
        "cpu_status",
        "get_cpu_status",
        "get_gpu_processes",
        "get_gpu_status",
    }
    assert required.issubset(names)


def test_integration_state(agent_tools: list) -> None:
    state = verify_agent_integration_state()
    assert state.discovered is True
    assert state.selectable is True
    assert state.tool_count >= 4


@pytest.mark.parametrize("scenario", DETERMINISTIC_SCENARIOS, ids=lambda s: s.scenario_id)
def test_deterministic_routing(scenario, agent_tools: list) -> None:
    result = run_e2e_scenario(scenario, tools=agent_tools)
    assert result.routing_match is True, result.to_dict()


def test_get_gpu_status_no_stub_constants(agent_tools: list) -> None:
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
            "rows": [["GeForce TEST", "41", "7", "1234", "8192"]],
            "source": "nvidia-smi",
        },
    ):
        rec = execute_registry_tool("get_gpu_status", {})
    out = rec.result
    assert out["gpu"] == "GeForce TEST"
    assert out["gpu"] != "RTX 3060"
    assert out["observation_source"] == "real"


def test_get_cpu_status_executes(agent_tools: list) -> None:
    rec = execute_registry_tool("get_cpu_status", {})
    assert isinstance(rec.result, dict)
    assert "model" in rec.result
    assert "physical_cores" in rec.result


def test_schema_snapshot_includes_get_cpu_status() -> None:
    snap = production_schema_snapshot()
    assert "get_cpu_status" in snap
    assert "get_gpu_status" in snap
