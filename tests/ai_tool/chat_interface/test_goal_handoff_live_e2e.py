from __future__ import annotations

import pytest

from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import _prepare_paths_only


def _handoff_packet() -> dict:
    return {
        "handoff_id": "gh-live",
        "goal": {"summary": "Create sandbox/hello.txt"},
        "scope": {
            "in_scope": ["sandbox/hello.txt exists"],
            "affected_paths": ["hello.txt"],
        },
        "acceptance_criteria": [
            {
                "id": "A1",
                "statement": "hello.txt exists in Dedicated Sandbox",
                "verification": "sandbox observation",
            }
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Create hello.txt in Dedicated Sandbox",
                "acceptance": ["hello.txt is created via create_file"],
                "verification": [],
                "dependencies": [],
            }
        ],
    }


@pytest.mark.live_llm
def test_handoff_live_turn_withholds_completed_when_work_remains(
    monkeypatch,
    tmp_path,
):
    from ai_tool.chat_interface.agent_turn import ollama_available

    live, err = ollama_available()
    if not live:
        pytest.skip(f"ollama unavailable: {err}")

    _prepare_paths_only(monkeypatch, tmp_path)
    session = empty_session("handoff-live")
    result = run_chat_turn(
        session,
        "Create hello.txt in Dedicated Sandbox",
        model=None,
        handoff_packet=_handoff_packet(),
    )
    stop = (result.get("runtime_status_report") or {}).get("reason_code")
    assert stop in {
        LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK.value,
        LoopStopReason.GOAL_INCOMPLETE_REPLAN.value,
        LoopStopReason.GOAL_INCOMPLETE_CONTINUATION.value,
        LoopStopReason.COMPLETED.value,
    }
    if stop == LoopStopReason.COMPLETED.value:
        tools = [row.get("name") for row in result.get("tools") or []]
        assert "create_file" in tools
