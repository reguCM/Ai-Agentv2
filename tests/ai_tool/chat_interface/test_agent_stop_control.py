"""Production Agent terminal stop control — hard stop fast-path and tool-count removal."""
from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.agent_stop_control import (
    is_hard_terminal_stop,
    is_resumable_pause_stop,
    should_skip_agent_llm_after_stop,
    should_system_fast_exit_after_stop,
)
from ai_tool.chat_interface.agent_turn import LoopStopReason, run_chat_turn
from ai_tool.chat_interface.chat_session import empty_session
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _response,
    _tool_call,
)


def _recording_chat(responses):
    rows = list(responses)
    calls: list[str] = []

    def chat(**_kwargs):
        calls.append("llm")
        if not rows:
            return _response("")
        return rows.pop(0)

    chat.call_log = calls
    return chat


def test_tool_count_above_20_does_not_stop_by_count_only(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_tool_absolute_hard_limit": 20,
            "agent_stagnation_limit": 99,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": True,
        },
    )
    responses = []
    for index in range(25):
        responses.append(
            _response(calls=[_tool_call("read_file", {"path": f"file_{index}.md"})])
        )
    responses.append(_response("done"))
    chat = _recording_chat(responses)
    result = run_chat_turn(
        empty_session("tool-count-telemetry"),
        "file audit",
        chat_fn=chat,
        model="fake",
    )
    assert result["loop_counters"]["total_tool_calls"] == 25
    assert result["loop_counters"]["configured_tool_limit"] == 20
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") != "TOOL_HARD_LIMIT"


def test_production_default_stops_on_stagnation_without_warning_flag(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response("unused"),
    ]
    chat = _recording_chat(responses)
    result = run_chat_turn(
        empty_session("production-default-stagnation"),
        "file audit",
        chat_fn=chat,
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    assert result.get("system_fast_exit") is True
    assert len(chat.call_log) == 3
    assert result["loop_counters"]["total_tool_calls"] == 3


def test_production_stops_on_same_failure_limit(tmp_path, monkeypatch):
    _prepare(
        monkeypatch,
        tmp_path,
        {"ok": False, "status": "failure", "error": "read failed"},
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 99,
            "agent_same_failure_limit": 2,
            "agent_no_evidence_limit": 99,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "missing.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "missing.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "missing.md"})]),
    ]
    chat = _recording_chat(responses)
    result = run_chat_turn(
        empty_session("same-failure-stop"),
        "file audit",
        chat_fn=chat,
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "SAME_FAILURE_LIMIT"
    assert result.get("system_fast_exit") is True
    assert len(chat.call_log) == 2
    assert result["loop_counters"]["total_tool_calls"] == 2


def test_production_stops_on_no_evidence_limit(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 99,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 3,
        },
    )
    responses = []
    for index in range(6):
        responses.append(
            _response(
                calls=[_tool_call("read_file", {"path": f"distinct_{index}.md"})]
            )
        )
    chat = _recording_chat(responses)
    result = run_chat_turn(
        empty_session("no-evidence-stop"),
        "file audit",
        chat_fn=chat,
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "NO_EVIDENCE_LIMIT"
    assert result.get("system_fast_exit") is True
    assert result["loop_counters"]["total_tool_calls"] >= 3


def test_healthy_progress_does_not_hit_semantic_fuse(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 3,
            "agent_same_failure_limit": 3,
            "agent_no_evidence_limit": 6,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "a.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "b.md"})]),
        _response("done"),
    ]
    result = run_chat_turn(
        empty_session("healthy-progress"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    assert result.get("stop_reason") in {None, "COMPLETED"}
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") not in {
        "STAGNATION_LIMIT",
        "SAME_FAILURE_LIMIT",
        "NO_EVIDENCE_LIMIT",
    }


def test_hard_stop_skips_final_synthesis_llm(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": False,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response("should-not-be-used"),
    ]
    chat = _recording_chat(responses)
    result = run_chat_turn(
        empty_session("hard-stop-no-synthesis"),
        "file audit",
        chat_fn=chat,
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    assert should_skip_agent_llm_after_stop(LoopStopReason.STAGNATION_LIMIT)
    assert is_hard_terminal_stop(LoopStopReason.STAGNATION_LIMIT)
    assert len(chat.call_log) == 3
    assert result["answer"]
    assert "停止理由" in result["answer"]


def test_hard_stop_blocks_additional_tool_calls(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": False,
        },
    )
    responses = [
        _response(
            calls=[
                _tool_call("read_file", {"path": "same.md"}),
                _tool_call("read_file", {"path": "same.md"}),
            ]
        ),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response("unused"),
    ]
    result = run_chat_turn(
        empty_session("hard-stop-no-extra-tools"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    assert result["loop_counters"]["total_tool_calls"] == 3


def test_hard_stop_persists_mission_memory(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": False,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
    ]
    result = run_chat_turn(
        empty_session("hard-stop-persist"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    recorded = result.get("mission_memory") or {}
    assert recorded.get("mission_id")
    assert recorded.get("execution_id")
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
    assert result["task_runtime"]["current_task_id"]
    memory_events = [
        item for item in result.get("events") or [] if item.get("type") == "mission_memory"
    ]
    assert memory_events
    assert memory_events[-1].get("status") == "saved"


def test_safety_and_cancel_stops_skip_extra_llm(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)

    timeout_calls: list[str] = []

    def timeout(**_kwargs):
        timeout_calls.append("llm")
        raise TimeoutError("LLM timed out")

    result_timeout = run_chat_turn(
        empty_session("safety-timeout"),
        "file audit",
        chat_fn=timeout,
        model="fake",
    )
    assert result_timeout["runtime_status_report"]["reason_code"] == "TIMEOUT"
    assert len(timeout_calls) == 1

    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    from ai_tool.chat_interface.activity_status import request_cancel, snapshot_activity

    session = empty_session("safety-cancel")
    cancel_calls: list[str] = []

    def wrapped(**_kwargs):
        active = snapshot_activity("safety-cancel")
        request_cancel("safety-cancel", str(active["turn_id"]))
        cancel_calls.append("llm")
        return _response("late answer")

    result_cancel = run_chat_turn(
        session,
        "file audit",
        chat_fn=wrapped,
        model="fake",
    )
    assert result_cancel["runtime_status_report"]["reason_code"] == "USER_CANCELLED"
    assert len(cancel_calls) == 1


def test_capability_gap_terminal_skips_agent_llm(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.tool_calling_capability_bridge.TOOL_CALLING_FALLBACK_CANDIDATES",
        (),
    )

    def must_not_run(**_kwargs):
        raise AssertionError("LLM must not run after terminal capability gap")

    result = run_chat_turn(
        empty_session("cap-gap-terminal"),
        "file audit",
        chat_fn=must_not_run,
        model="deepseek_coder_v2_16b",
    )
    assert result["runtime_status_report"]["reason_code"] == "HARD_CAPABILITY_GAP"
    assert should_skip_agent_llm_after_stop(LoopStopReason.HARD_CAPABILITY_GAP)
    assert not should_system_fast_exit_after_stop(LoopStopReason.HARD_CAPABILITY_GAP)
    assert is_resumable_pause_stop(LoopStopReason.HUMAN_GRILL)


def test_resumable_pause_classification():
    assert is_resumable_pause_stop(LoopStopReason.HUMAN_GRILL)
    assert is_resumable_pause_stop(LoopStopReason.APPROVAL_REQUIRED)
    assert not is_resumable_pause_stop(LoopStopReason.STAGNATION_LIMIT)


def test_hard_stop_fast_exit_skips_gap_resolution_router(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": False,
        },
    )

    def _forbidden_router(*_args, **_kwargs):
        raise AssertionError("gap_resolution router must not run after system fast exit")

    monkeypatch.setattr(
        "ai_tool.chat_interface.gap_resolution_router.route_gap_resolution_from_orchestrator",
        _forbidden_router,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.gap_resolution_router.observe_gap_resolution_at_execution_end",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("gap_resolution observe must not run after system fast exit")
        ),
    )

    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
    ]
    result = run_chat_turn(
        empty_session("fast-exit-no-gap-router"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    assert result["system_fast_exit"] is True
    assert result["gap_resolution"] is None
    assert not any(
        item.get("type") == "gap_resolution_routed" for item in result.get("events") or []
    )


def test_hard_stop_fast_exit_preserves_task_runtime_without_gate_finish(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 99,
            "agent_no_evidence_limit": 99,
            "semantic_stagnation_warning_enabled": False,
        },
    )

    def _forbidden_gate(_answer):
        raise AssertionError("gate_answer must not run after system fast exit")

    def _forbidden_finish(*_args, **_kwargs):
        raise AssertionError("finish must not run after system fast exit")

    monkeypatch.setattr(
        "ai_tool.chat_interface.task_orchestration.ChatTaskOrchestrator.gate_answer",
        _forbidden_gate,
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.task_orchestration.ChatTaskOrchestrator.finish",
        _forbidden_finish,
    )

    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
    ]
    result = run_chat_turn(
        empty_session("fast-exit-runtime-preserved"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    runtime = result["task_runtime"]
    assert runtime is not None
    assert result["system_fast_exit"] is True
    assert result["gap_resolution"] is None
    goals = runtime.get("goals") or []
    assert goals
    assert goals[0].get("status") != "complete"
    assert result["runtime_status_report"]["reason_code"] == "STAGNATION_LIMIT"
