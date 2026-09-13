from __future__ import annotations

from types import SimpleNamespace

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator, build_tool_expectation
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
)


def _handoff_packet() -> dict:
    return {
        "handoff_id": "gh-runtime-e2e",
        "goal": {"summary": "Create tetris/main.py in Dedicated Sandbox"},
        "scope": {
            "in_scope": ["tetris/main.py exists in Dedicated Sandbox"],
            "affected_paths": ["tetris/main.py"],
        },
        "acceptance_criteria": [
            {
                "id": "A1",
                "statement": "tetris/main.py exists in Dedicated Sandbox",
                "verification": "sandbox observation",
            }
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Create tetris/main.py in Dedicated Sandbox",
                "acceptance": ["tetris/main.py is created in Dedicated Sandbox"],
                "verification": ["create_file succeeds"],
                "dependencies": [],
            }
        ],
    }


def test_handoff_task_builds_create_file_expectation():
    registry = load_registry_tools()
    llm_tools = [
        item for item in registry if item.get("visibility") == "agent" and item.get("name")
    ]
    orchestrator = ChatTaskOrchestrator("expect", "implement tetris")
    seed_orchestrator_from_handoff(orchestrator, _handoff_packet())
    orchestrator.configure_tool_expectation(llm_tools, registry_tools=registry)
    expectation = orchestrator.tool_expectation
    assert expectation.generated is True
    assert expectation.required_capability == "workspace_file_create"
    assert expectation.expected_tool == "create_file"
    assert expectation.expected_arguments.get("path") == "tetris/main.py"


def test_build_tool_expectation_prefers_current_task_over_request():
    tools = [
        {"type": "function", "function": {"name": "create_file"}},
    ]
    task = SimpleNamespace(
        title="Create tetris/main.py in Dedicated Sandbox",
        instruction="Affected paths:\n- tetris/main.py",
    )
    expectation = build_tool_expectation(
        "仕様を確認してください",
        tools,
        task=task,
    )
    assert expectation.generated is True
    assert expectation.expected_tool == "create_file"
    assert expectation.expected_arguments.get("path") == "tetris/main.py"


def test_incomplete_handoff_goal_cannot_stop_completed(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.task_orchestration.ChatTaskOrchestrator.recovery_hint",
        lambda self: None,
    )
    session = empty_session("handoff-guard")
    result = run_chat_turn(
        session,
        "Create tetris/main.py in Dedicated Sandbox",
        chat_fn=_chat_sequence(
            _response("I will describe the code in markdown."),
            _response("Goal remains incomplete; mutation was not executed."),
        ),
        model="fake",
        handoff_packet=_handoff_packet(),
    )
    assert result.get("error") is None
    stop_reason = (result.get("runtime_status_report") or {}).get("reason_code")
    assert stop_reason in {
        LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK.value,
        LoopStopReason.GOAL_INCOMPLETE_REPLAN.value,
        LoopStopReason.GOAL_INCOMPLETE_CONTINUATION.value,
    }
    assert stop_reason != LoopStopReason.COMPLETED.value
    runtime = result.get("task_runtime") or {}
    tasks = {row["task_id"]: row for row in runtime.get("tasks") or []}
    assert "gh-T1" in tasks
    assert tasks["gh-T1"]["source"] == "goal_handoff"
    assert tasks["gh-T1"]["source_task_id"] == "T1"


def test_coerce_task_string_list_repair_in_normalize_tasks():
    from ai_tool.dev_skill_pipeline import coerce_task_string_list, normalize_implementation_tasks

    repaired = coerce_task_string_list(list("Piececlasshandlesrotation"))
    assert repaired == ["Piececlasshandlesrotation"]
    rows = normalize_implementation_tasks(
        [
            {
                "id": "task-1",
                "title": "Core structures",
                "acceptance": list("Piececlasshandlesrotation"),
                "verification": [],
                "dependencies": [],
            }
        ],
        default_acceptance=["fallback"],
        default_verification=[],
    )
    assert rows[0]["acceptance"] == ["Piececlasshandlesrotation"]
