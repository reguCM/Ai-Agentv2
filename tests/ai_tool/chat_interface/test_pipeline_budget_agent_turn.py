"""Production Chat pipeline budget wiring during run_chat_turn."""
from __future__ import annotations

import time
from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.pipeline_observations import PipelineObserver
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _prepare,
    _response,
    _tool_call,
)


def _chat_sequence(*responses):
    rows = list(responses)

    def chat(**_kwargs):
        return rows.pop(0)

    return chat


def test_run_chat_turn_stops_when_pipeline_budget_exceeded(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 99,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
        },
    )
    observer = PipelineObserver(tmp_path / "run", budget_seconds=0.05)
    observer.set_work_plan(composition_steps=[], include_production_chat=True)
    time.sleep(0.06)
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "a.md"})]),
        _response("unused"),
    ]
    llm_calls: list[str] = []

    def chat(**_kwargs):
        llm_calls.append("llm")
        return responses.pop(0)

    result = run_chat_turn(
        empty_session("pipeline-budget-stop"),
        "file audit",
        chat_fn=chat,
        model="fake",
        pipeline_observer=observer,
    )
    assert result["runtime_status_report"]["reason_code"] == "PIPELINE_BUDGET_EXCEEDED"
    assert result.get("system_fast_exit") is True
    assert len(llm_calls) == 0
    assert result["loop_counters"]["total_tool_calls"] == 0
    budget_events = [
        item for item in result["events"] if item.get("type") == "pipeline_budget"
    ]
    assert budget_events
    assert budget_events[-1]["status"] == "exceeded"


def test_run_chat_turn_without_observer_ignores_budget(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 99,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
        },
    )
    result = run_chat_turn(
        empty_session("no-observer"),
        "file audit",
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("read_file", {"path": "a.md"})]),
            _response("done"),
        ),
        model="fake",
    )
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") != "PIPELINE_BUDGET_EXCEEDED"
