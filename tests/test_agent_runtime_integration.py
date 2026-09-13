"""Execute the real agent.py loop hooks with local fakes and no module side effects."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from tools.ai.agent_runtime import AgentRuntime, AgentRuntimeState
from tools.system.tool_result_contract import normalize_tool_result


AGENT_PATH = Path(__file__).resolve().parents[1] / "agent.py"


def _agent_loop_code() -> Any:
    """Compile only the real Tool Loop and final COMPLETED hook from agent.py."""
    tree = ast.parse(AGENT_PATH.read_text(encoding="utf-8-sig"))
    loop = next(
        node
        for node in tree.body
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "range"
        and any(
            isinstance(child, ast.Name) and child.id == "MAX_TOOL_ROUNDS"
            for child in ast.walk(node)
        )
    )
    completed = next(
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and "AgentRuntimeState.COMPLETED" in ast.unparse(node)
    )
    module = ast.fix_missing_locations(ast.Module(body=[loop, completed], type_ignores=[]))
    return compile(module, str(AGENT_PATH), "exec")


def _response(*tool_names: str) -> Any:
    calls = [
        SimpleNamespace(function=SimpleNamespace(name=name, arguments={}))
        for name in tool_names
    ]
    return SimpleNamespace(message=SimpleNamespace(tool_calls=calls, content="done"))


def _run_real_loop(
    responses: list[Any],
    *,
    execute: Callable[[str, dict[str, Any]], Any] | None = None,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AgentRuntime, list[Any]]:
    runtime = AgentRuntime(logger=None)
    pending = list(responses)
    messages: list[Any] = []

    def fake_chat(**_kwargs: Any) -> Any:
        return pending.pop(0)

    def fake_execute(tool_name: str, arguments: dict[str, Any], **_kwargs: Any) -> Any:
        if execute is not None:
            return execute(tool_name, arguments)
        return {"ok": True, "tool": tool_name}

    monkeypatch.setattr(
        "tools.system.network.web_evidence.enrich_web_tool_result",
        lambda _name, result: result,
    )
    namespace = {
        "MAX_TOOL_ROUNDS": len(responses),
        "AgentRuntimeState": AgentRuntimeState,
        "normalize_tool_result": normalize_tool_result,
        "agent_runtime": runtime,
        "chat": fake_chat,
        "MODEL": "fake-model",
        "messages": messages,
        "tools": [],
        "ollama_tools_for_llm": lambda value: value,
        "try_agent_recovery_evaluation_loop": lambda **_kwargs: None,
        "print_agent_recovery_stop_notice": lambda _value: None,
        "proposal_instruction_added": False,
        "_agent_recovery_stop": False,
        "related_tools": [],
        "reference_tools": [],
        "reference_sources": [],
        "execute_tool": fake_execute,
        "web_session_tracker": None,
        "agent_tools_tried": [],
        "build_tool_trial": lambda name, arguments, result: {
            "name": name,
            "arguments": arguments,
            "result": result,
        },
        "json": json,
        "print_tool_result_for_stdout": lambda _name, _result: None,
        "PROPOSAL_INSTRUCTIONS": "proposal",
    }
    exec(_agent_loop_code(), namespace)
    return runtime, messages


def _states(runtime: AgentRuntime) -> list[str]:
    return [item["state"] for item in runtime.state_history]


def test_real_hook_normal_chat_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, _ = _run_real_loop([_response()], monkeypatch=monkeypatch)
    assert _states(runtime) == ["IDLE", "THINKING", "COMPLETED"]


def test_real_hook_tool_success_and_raw_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, messages = _run_real_loop(
        [_response("read_file"), _response()],
        monkeypatch=monkeypatch,
    )
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
    assert any(item.get("role") == "tool" for item in messages if isinstance(item, dict))


@pytest.mark.parametrize(
    "result",
    [
        {"ok": True, "status": "partial", "error": None, "warnings": []},
        {"ok": True, "truncated": True, "error": "limit reached"},
    ],
)
def test_real_hook_v1_and_legacy_partial_observe_then_rethink(
    result: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _ = _run_real_loop(
        [_response("search_files"), _response()],
        execute=lambda _name, _arguments: result,
        monkeypatch=monkeypatch,
    )
    states = _states(runtime)
    partial_at = states.index("TOOL_PARTIAL")
    assert states[partial_at : partial_at + 3] == [
        "TOOL_PARTIAL",
        "OBSERVING",
        "THINKING",
    ]
    assert runtime.last_error is None
    assert runtime.current_tool is None


def test_real_hook_ambiguous_legacy_result_is_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, _ = _run_real_loop(
        [_response("read_file"), _response()],
        execute=lambda _name, _arguments: {},
        monkeypatch=monkeypatch,
    )
    assert "TOOL_FAILED" in _states(runtime)
    assert "TOOL_SUCCESS" not in _states(runtime)


def test_real_hook_multiple_tools_keep_success_and_partial_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = {
        "read_file": {"ok": True, "error": None},
        "search_files": {"ok": True, "truncated": True, "error": "limit"},
    }
    runtime, _ = _run_real_loop(
        [_response("read_file", "search_files"), _response()],
        execute=lambda name, _arguments: results[name],
        monkeypatch=monkeypatch,
    )
    terminal_events = [
        (item["state"], item["tool"])
        for item in runtime.state_history
        if item["state"] in {"TOOL_SUCCESS", "TOOL_PARTIAL", "TOOL_FAILED"}
    ]
    assert terminal_events == [
        ("TOOL_SUCCESS", "read_file"),
        ("TOOL_PARTIAL", "search_files"),
    ]
    assert runtime.tool_call_count == 2
    assert runtime.current_tool is None


def test_real_hook_tool_failure_observes_then_rethinks(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime, _ = _run_real_loop(
        [_response("read_file"), _response()],
        execute=lambda _name, _arguments: {"ok": False, "error": "failed"},
        monkeypatch=monkeypatch,
    )
    states = _states(runtime)
    failed_at = states.index("TOOL_FAILED")
    assert states[failed_at : failed_at + 3] == ["TOOL_FAILED", "OBSERVING", "THINKING"]
    assert runtime.last_error == "failed"
    assert runtime.current_tool is None


def test_real_hook_exception_records_error_and_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, AgentRuntime] = {}

    original_init = AgentRuntime.__post_init__

    def remember_runtime(runtime: AgentRuntime) -> None:
        original_init(runtime)
        captured["runtime"] = runtime

    monkeypatch.setattr(AgentRuntime, "__post_init__", remember_runtime)

    def fail(_name: str, _arguments: dict[str, Any]) -> Any:
        raise RuntimeError("tool exploded")

    runtime = AgentRuntime(logger=None)
    captured["runtime"] = runtime
    pending = [_response("read_file")]
    namespace = {
        "MAX_TOOL_ROUNDS": 1,
        "AgentRuntimeState": AgentRuntimeState,
        "normalize_tool_result": normalize_tool_result,
        "agent_runtime": runtime,
        "chat": lambda **_kwargs: pending.pop(0),
        "MODEL": "fake-model",
        "messages": [],
        "tools": [],
        "ollama_tools_for_llm": lambda value: value,
        "try_agent_recovery_evaluation_loop": lambda **_kwargs: None,
        "proposal_instruction_added": False,
        "_agent_recovery_stop": False,
        "related_tools": [],
        "reference_tools": [],
        "reference_sources": [],
        "execute_tool": lambda name, arguments, **_kwargs: fail(name, arguments),
        "web_session_tracker": None,
        "agent_tools_tried": [],
        "build_tool_trial": lambda *_args: {},
        "json": json,
        "print_tool_result_for_stdout": lambda *_args: None,
        "PROPOSAL_INSTRUCTIONS": "proposal",
    }
    with pytest.raises(RuntimeError, match="tool exploded"):
        exec(_agent_loop_code(), namespace)
    assert runtime.current_state is AgentRuntimeState.ERROR
    assert runtime.last_error == "RuntimeError: tool exploded"
