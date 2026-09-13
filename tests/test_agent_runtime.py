from __future__ import annotations

import pytest

from tools.ai.agent_runtime import AgentRuntime, AgentRuntimeState


def _states(runtime: AgentRuntime) -> list[str]:
    return [item["state"] for item in runtime.state_history]


def test_normal_chat_idle_thinking_completed() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.THINKING)
    runtime.transition(AgentRuntimeState.COMPLETED)

    assert _states(runtime) == ["IDLE", "THINKING", "COMPLETED"]


def test_tool_calling_basic_transitions() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.THINKING)
    runtime.transition(AgentRuntimeState.TOOL_CALL_REQUESTED, tool="read_file")
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="read_file")
    runtime.transition(AgentRuntimeState.TOOL_SUCCESS, tool="read_file")
    runtime.transition(AgentRuntimeState.OBSERVING, tool="read_file")
    runtime.transition(AgentRuntimeState.THINKING)
    runtime.transition(AgentRuntimeState.COMPLETED)

    assert _states(runtime) == [
        "IDLE",
        "THINKING",
        "TOOL_CALL_REQUESTED",
        "TOOL_RUNNING",
        "TOOL_SUCCESS",
        "OBSERVING",
        "THINKING",
        "COMPLETED",
    ]
    assert runtime.tool_call_count == 1


def test_tool_running_to_success() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="search_files")
    runtime.transition(AgentRuntimeState.TOOL_SUCCESS, tool="search_files")

    assert runtime.current_state is AgentRuntimeState.TOOL_SUCCESS
    assert runtime.current_tool is None
    assert runtime.state_history[-1]["tool"] == "search_files"


def test_tool_running_to_partial_preserves_tool_without_setting_error() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="search_files")
    runtime.transition(AgentRuntimeState.TOOL_PARTIAL, tool="search_files")

    assert runtime.current_state is AgentRuntimeState.TOOL_PARTIAL
    assert runtime.current_tool is None
    assert runtime.state_history[-1]["tool"] == "search_files"
    assert runtime.last_error is None


def test_tool_running_to_failed() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="read_file")
    runtime.transition(
        AgentRuntimeState.TOOL_FAILED,
        tool="read_file",
        error="file unavailable",
    )

    assert runtime.current_state is AgentRuntimeState.TOOL_FAILED
    assert runtime.current_tool is None
    assert runtime.state_history[-1]["tool"] == "read_file"
    assert runtime.last_error == "file unavailable"


def test_state_history_snapshot_is_saved_as_plain_data() -> None:
    runtime = AgentRuntime(session_id="session-1", logger=None)
    runtime.transition(AgentRuntimeState.THINKING)
    snapshot = runtime.snapshot()

    assert snapshot["session_id"] == "session-1"
    assert snapshot["state_history"][0]["state"] == "IDLE"
    assert snapshot["state_history"][1]["timestamp"].endswith("Z")
    assert set(snapshot["state_history"][1]) == {"state", "timestamp", "tool", "error"}


def test_exception_transitions_to_error_and_is_reraised() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="read_file")

    with pytest.raises(RuntimeError, match="boom"):
        with runtime.error_boundary():
            raise RuntimeError("boom")

    assert runtime.current_state is AgentRuntimeState.ERROR
    assert runtime.current_tool is None
    assert runtime.state_history[-1]["tool"] == "read_file"
    assert runtime.last_error == "RuntimeError: boom"


def test_multiple_tool_calls_keep_each_tool_in_history() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.THINKING)
    # TOOL_CALL_REQUESTED describes the LLM response as a whole, so it occurs once.
    runtime.transition(AgentRuntimeState.TOOL_CALL_REQUESTED, tool="read_file")

    for tool in ("read_file", "search_files"):
        runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool=tool)
        runtime.transition(AgentRuntimeState.TOOL_SUCCESS, tool=tool)
        runtime.transition(AgentRuntimeState.OBSERVING)

    running = [
        item for item in runtime.state_history if item["state"] == "TOOL_RUNNING"
    ]
    succeeded = [
        item for item in runtime.state_history if item["state"] == "TOOL_SUCCESS"
    ]
    assert runtime.tool_call_count == 2
    assert [item["tool"] for item in running] == ["read_file", "search_files"]
    assert [item["tool"] for item in succeeded] == ["read_file", "search_files"]
    assert runtime.current_tool is None


def test_failure_can_return_to_thinking_when_recovery_is_disabled() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="read_file")
    runtime.transition(AgentRuntimeState.TOOL_FAILED, error="not found")
    runtime.transition(AgentRuntimeState.OBSERVING)
    runtime.transition(AgentRuntimeState.THINKING)

    assert _states(runtime)[-4:] == [
        "TOOL_RUNNING",
        "TOOL_FAILED",
        "OBSERVING",
        "THINKING",
    ]
    assert runtime.current_tool is None
    assert runtime.last_error == "not found"


def test_history_tail_always_matches_current_state() -> None:
    runtime = AgentRuntime(logger=None)
    for state in (
        AgentRuntimeState.THINKING,
        AgentRuntimeState.TOOL_CALL_REQUESTED,
        AgentRuntimeState.TOOL_RUNNING,
        AgentRuntimeState.TOOL_SUCCESS,
        AgentRuntimeState.TOOL_PARTIAL,
        AgentRuntimeState.OBSERVING,
        AgentRuntimeState.COMPLETED,
    ):
        runtime.transition(state, tool="read_file" if "TOOL" in state.value else None)
        assert runtime.state_history[-1]["state"] == runtime.current_state.value


def test_last_error_means_most_recent_error_and_survives_success() -> None:
    runtime = AgentRuntime(logger=None)
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="read_file")
    runtime.transition(AgentRuntimeState.TOOL_FAILED, error="first failure")
    runtime.transition(AgentRuntimeState.TOOL_RUNNING, tool="search_files")
    runtime.transition(AgentRuntimeState.TOOL_SUCCESS)

    assert runtime.last_error == "first failure"
    assert runtime.current_tool is None
