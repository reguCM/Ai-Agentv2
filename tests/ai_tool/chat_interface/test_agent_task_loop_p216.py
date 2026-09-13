import json
from types import SimpleNamespace

import pytest

from ai_tool.chat_interface.activity_status import (
    ActivityStatus,
    activity_message,
    begin_turn,
    finish_turn,
    request_cancel,
    response_is_current,
    snapshot_activity,
    update_activity,
)
from ai_tool.chat_interface.agent_turn import (
    LoopCounters,
    LoopStopReason,
    _chat_turn,
    _resolve_runtime_model_name,
    run_chat_turn,
)
from tests.ai_tool.chat_interface.execution_end_invariants import (
    execution_stop_reason_from_result,
)
from ai_tool.chat_interface.activity import session_activity
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.task_orchestration import (
    AGENT_CORE_PROMPT,
    ChatTaskOrchestrator,
    build_tool_expectation,
    is_agent_task,
)
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
)


def _response(content="", calls=None):
    return SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls or [])
    )


def _tool_call(name, arguments=None):
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=arguments or {})
    )


def _chat_sequence(*responses):
    rows = list(responses)

    def chat(**_kwargs):
        return rows.pop(0)

    return chat


def _prepare(monkeypatch, tmp_path, result=None):
    monkeypatch.setenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", "1")
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [RequirementCondition("C1", "relevant evidence observed")], "READY"
        ),
    )
    if result is not None:
        monkeypatch.setattr(
            "ai_tool.chat_interface.agent_turn._execute_agent_tool",
            lambda *_args, **_kwargs: result,
        )


def _prepare_paths_only(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", "1")
    monkeypatch.setattr(
        "ai_tool.mission_memory.store.default_store_root",
        lambda: tmp_path / "mission_memory",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions"
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )


def test_01_agent_request_classification():
    assert is_agent_task("Repositoryを調査して実装計画を作る")


def test_02_simple_chat_classification():
    assert not is_agent_task("こんにちは")


def test_explicit_agent_visible_tool_reference_is_agent_task():
    assert is_agent_task(
        "現在時刻を get_system_time で実測してください",
        known_tool_names={"get_system_time"},
    )


def test_natural_language_live_observation_is_agent_task():
    tools = [{
        "name": "clock_tool",
        "visibility": "agent",
        "observation_source": "real",
        "keywords": ["日時", "タイムゾーン", "CPU使用率"],
    }]
    assert is_agent_task(
        "今の日時とタイムゾーンを教えて",
        agent_visible_tools=tools,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Pythonとは何ですか",
        "この文章を言い換えて",
        "こんにちは。雑談しましょう",
        "一般知識としてCPU使用率とは何ですか",
    ],
)
def test_general_chat_is_not_promoted_by_observation_registry(text):
    tools = [{
        "name": "clock_tool",
        "visibility": "agent",
        "observation_source": "real",
        "keywords": ["日時", "タイムゾーン", "CPU使用率"],
    }]
    assert not is_agent_task(text, agent_visible_tools=tools)


def test_unknown_identifier_alone_is_not_agent_task():
    assert not is_agent_task(
        "unknown_runtime_field の意味は何ですか",
        known_tool_names={"get_system_time"},
    )


def test_profile_id_is_resolved_to_ollama_model_name():
    assert _resolve_runtime_model_name("qwen3_14b", {}) == "qwen3:14b"
    assert _resolve_runtime_model_name("custom:model", {}) == "custom:model"


def test_requirement_transport_failure_is_reported_as_communication_blocked(monkeypatch, tmp_path):
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.delenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", raising=False)

    def failed_chat(**_kwargs):
        raise RuntimeError("provider unavailable")

    result = run_chat_turn(
        empty_session("requirement-transport-failure"),
        "現在時刻を get_system_time で実測してください",
        chat_fn=failed_chat,
        model="fake:model",
    )

    assert result["execution_diagnostics"]["communication_status"] == "FAILED"
    assert result["execution_diagnostics"]["failure_phase"] == "requirement_resolution"
    assert result.get("requirement_decomposition", {}).get("source") == "requirement_resolution"
    assert result["execution_diagnostics"]["exception_type"] == "RuntimeError"
    assert result["runtime_status_report"]["reason_code"] == "COMMUNICATION_FAILURE"


def test_03_final_goal_and_initial_subgoal_are_created():
    orchestrator = ChatTaskOrchestrator("turn", "repository audit")
    orchestrator.initialize()
    assert orchestrator.runtime.goals["G1"].title == "repository audit"
    assert orchestrator.runtime.goals["G1.1"].parent_goal_id == "G1"


def test_04_small_task_has_explicit_completion_conditions():
    orchestrator = ChatTaskOrchestrator("turn", "repository audit")
    orchestrator.initialize()
    assert orchestrator.runtime.tasks["T1"].completion_conditions == [
        "relevant evidence observed"
    ]
    assert orchestrator.runtime.tasks["T2"].completion_conditions == ["answer produced"]


def test_05_hint_contains_only_current_task_context():
    orchestrator = ChatTaskOrchestrator("turn", "repository audit")
    orchestrator.initialize()
    hint = orchestrator.hint()
    assert "Current Task:" in hint and "Completion Condition:" in hint


def test_06_tool_success_completes_observation_but_not_answer_task():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    orchestrator.observe_tool(
        "read_file", {}, {"status": "success"}, {"path": "x"}, relevant_tools=["read_file"]
    )
    assert orchestrator.runtime.tasks["T1"].status == "complete"
    assert orchestrator.runtime.tasks["T2"].status == "pending"
    assert orchestrator.current_task_id == "T2"


def test_07_partial_with_evidence_is_progress():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    orchestrator.observe_tool(
        "search_files", {}, {"status": "partial"}, {"matches": 1}, relevant_tools=["search_files"]
    )
    assert orchestrator.runtime.tasks["T1"].progress_state == "progress"


def test_08_irrelevant_result_is_not_evidence():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    audit = orchestrator.observe_tool(
        "get_system_summary", {}, {"status": "success"}, {}, relevant_tools=["read_file"]
    )
    assert audit == "REJECT_ACTION_RESULT"
    assert orchestrator.task.evidence_ids == []


def test_relevant_tools_follow_registry_metadata_for_new_tool():
    orchestrator = ChatTaskOrchestrator("turn", "現在の気圧を取得する")
    orchestrator.initialize()
    provider_tools = [
        {"type": "function", "function": {"name": "observe_pressure"}},
        {"type": "function", "function": {"name": "observe_market"}},
    ]
    registry_tools = [
        {
            "name": "observe_pressure",
            "visibility": "agent",
            "observation_source": "real",
            "keywords": ["気圧"],
            "module": "tools.fake.pressure",
            "function": "observe_pressure",
            "input": {},
        },
        {
            "name": "observe_market",
            "visibility": "agent",
            "observation_source": "real",
            "keywords": ["株価"],
            "module": "tools.fake.market",
            "function": "observe_market",
            "input": {},
        },
    ]
    orchestrator.configure_tool_expectation(
        provider_tools, registry_tools=registry_tools
    )

    assert orchestrator.relevant_tools(provider_tools) == ["observe_pressure"]


def test_relevant_structured_success_result_becomes_evidence():
    orchestrator = ChatTaskOrchestrator("turn", "現在時刻を実測する")
    orchestrator.initialize()
    tools = [
        {
            "type": "function",
            "function": {"name": "get_system_time", "parameters": {"type": "object"}},
        }
    ]

    audit = orchestrator.observe_tool(
        "get_system_time",
        {},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"datetime": "2026-09-05T12:00:00+09:00", "timezone": "JST"},
        relevant_tools=orchestrator.relevant_tools(tools),
        raw_result={
            "datetime": "2026-09-05T12:00:00+09:00",
            "timezone": "JST",
            "ok": True,
            "status": "ok",
            "error": None,
        },
    )

    assert audit == "ACCEPT"
    assert len(orchestrator.runtime.evidence) == 1
    evidence = next(iter(orchestrator.runtime.evidence.values()))
    assert evidence.tool_name == "get_system_time"
    assert "2026-09-05T12:00:00+09:00" in (evidence.relevant_content or "")


def test_structured_observation_completes_only_supported_task_conditions():
    orchestrator = ChatTaskOrchestrator(
        "turn",
        "現在時刻とタイムゾーンを実測する",
        completion_conditions=[
            "get_system_timeで現在時刻が実測されている",
            "タイムゾーンが取得されている",
        ],
    )
    orchestrator.initialize()

    orchestrator.observe_tool(
        "get_system_time",
        {},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"datetime": "2026-09-05T12:00:00+09:00", "timezone": "JST"},
        relevant_tools=["get_system_time"],
        raw_result={
            "datetime": "2026-09-05T12:00:00+09:00",
            "timezone": "JST",
            "observation_source": "real",
            "ok": True,
            "status": "ok",
            "error": None,
        },
    )

    assert orchestrator.runtime.tasks["T1"].status == "complete"
    assert orchestrator.current_task_id == "T2"
    assert orchestrator.runtime.tasks["T2"].status == "pending"


def test_structured_observation_does_not_complete_unsupported_condition():
    orchestrator = ChatTaskOrchestrator(
        "turn",
        "現在時刻を実測する",
        completion_conditions=["CPU使用率が取得されている"],
    )
    orchestrator.initialize()

    orchestrator.observe_tool(
        "get_system_time",
        {},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"datetime": "2026-09-05T12:00:00+09:00"},
        relevant_tools=["get_system_time"],
        raw_result={
            "datetime": "2026-09-05T12:00:00+09:00",
            "observation_source": "real",
            "ok": True,
            "status": "ok",
            "error": None,
        },
    )

    assert orchestrator.runtime.tasks["T1"].status == "in_progress"


def test_failed_relevant_result_is_not_evidence():
    orchestrator = ChatTaskOrchestrator("turn", "現在時刻を実測する")
    orchestrator.initialize()

    audit = orchestrator.observe_tool(
        "get_system_time",
        {},
        {"ok": False, "status": "failure", "error": {"code": "clock_error"}},
        {"status": "failure"},
        relevant_tools=["get_system_time"],
        raw_result={"ok": False, "status": "failure", "error": "clock_error"},
    )

    assert audit == "ACCEPT"
    assert orchestrator.task.evidence_ids == []


def test_unrelated_structured_success_result_is_not_evidence():
    orchestrator = ChatTaskOrchestrator("turn", "ファイルを確認する")
    orchestrator.initialize()

    audit = orchestrator.observe_tool(
        "get_system_time",
        {},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"datetime": "2026-09-05T12:00:00+09:00"},
        relevant_tools=["read_file"],
        raw_result={
            "datetime": "2026-09-05T12:00:00+09:00",
            "ok": True,
            "status": "ok",
            "error": None,
        },
    )

    assert audit == "REJECT_ACTION_RESULT"
    assert orchestrator.task.evidence_ids == []


def test_09_repeated_failure_produces_recovery_hint():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    for _ in range(2):
        orchestrator.observe_tool(
            "read_file",
            {"path": "missing"},
            {"status": "failure", "error": {"code": "path_not_found"}},
            {},
            relevant_tools=["read_file"],
        )
    assert "Do not repeat" in (orchestrator.recovery_hint() or "")


def test_10_local_replan_adds_task_without_reopening_completed_one():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    orchestrator.runtime.evaluate_task(
        "T1", ["relevant evidence observed"]
    )
    orchestrator.add_local_replan("boundary", "inspect boundary")
    assert orchestrator.runtime.tasks["T1"].status == "complete"
    assert "T3" in orchestrator.runtime.tasks


def test_11_final_synthesis_requires_evidence_and_answer():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    assert not orchestrator.finish("answer")["ready"]


def test_12_final_synthesis_completes_after_evidence_and_answer():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    orchestrator.observe_tool(
        "read_file", {}, {"status": "success"}, {"fact": 1}, relevant_tools=["read_file"]
    )
    assert orchestrator.finish("answer")["ready"]


def test_13_core_prompt_requires_observation_and_completion_conditions():
    assert "推測せずToolで観測" in AGENT_CORE_PROMPT
    assert "Completion Condition" in AGENT_CORE_PROMPT


def test_14_llm_waiting_activity_message():
    assert activity_message(ActivityStatus.LLM_WAITING) == "LLMの応答を待っています…"


def test_15_tool_activity_shows_name_but_not_arguments():
    message = activity_message(ActivityStatus.TOOL_RUNNING, tool_name="read_file")
    assert message == "Toolを実行しています: read_file"
    assert "path" not in message


def test_16_heartbeat_becomes_long_running_without_failure():
    begin_turn("s16", "t16", "c16", clock=lambda: 0)
    update_activity("s16", "t16", ActivityStatus.LLM_WAITING, clock=lambda: 1)
    snap = snapshot_activity("s16", long_running_after=30, clock=lambda: 31)
    assert snap and snap["status"] == "LONG_RUNNING"
    assert snap["task_status"] is None


def test_17_activity_and_task_progress_are_independent():
    begin_turn("s17", "t17", "c17", clock=lambda: 0)
    update_activity(
        "s17",
        "t17",
        ActivityStatus.TOOL_RUNNING,
        task_status="in_progress",
        progress_state="stagnation",
        clock=lambda: 1,
    )
    snap = snapshot_activity("s17", clock=lambda: 2)
    assert snap and snap["status"] == "TOOL_RUNNING"
    assert snap["task_status"] == "in_progress"
    assert snap["progress_state"] == "stagnation"


def test_18_new_runtime_event_updates_activity():
    begin_turn("s18", "t18", "c18")
    assert update_activity("s18", "t18", ActivityStatus.RESULT_AUDITING)
    assert snapshot_activity("s18")["status"] == "RESULT_AUDITING"


def test_19_cancelled_turn_rejects_late_response():
    begin_turn("s19", "t19", "c19")
    assert request_cancel("s19", "t19")
    assert not response_is_current("s19", "t19")


def test_20_new_turn_rejects_previous_turn_response():
    begin_turn("s20", "old", "c-old")
    begin_turn("s20", "new", "c-new")
    assert not response_is_current("s20", "old")
    assert response_is_current("s20", "new")


def test_21_finished_turn_has_terminal_activity():
    begin_turn("s21", "t21", "c21")
    finish_turn("s21", "t21")
    assert snapshot_activity("s21")["status"] == "COMPLETED"


def test_22_simple_chat_gets_core_prompt_without_task_tree(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    captured = {}

    def chat(**kwargs):
        captured.update(kwargs)
        return _response("hello")

    result = run_chat_turn(empty_session("simple"), "こんにちは", chat_fn=chat, model="fake")
    assert AGENT_CORE_PROMPT in captured["messages"][0]["content"]
    assert result.get("task_runtime") is None


def test_23_agent_task_enters_real_chat_loop(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    result = run_chat_turn(
        empty_session("agent-task"), "repository audit plan", chat_fn=_chat_sequence(_response("answer")), model="fake"
    )
    assert result["task_runtime"]["goals"][0]["goal_id"] == "G1"


def test_24_tool_result_becomes_evidence_in_real_loop(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("answer"))
    result = run_chat_turn(empty_session("evidence"), "file audit", chat_fn=chat, model="fake")
    assert len(result["task_runtime"]["evidence"]) == 1
    assert result["final_synthesis"]["ready"]


def test_completion_contract_runtime_complete_reaches_completed(tmp_path, monkeypatch):
    """Completion Contract C1_RUNTIME_COMPLETE: runtime tasks/G1 complete → finish → COMPLETED.

    Proves RUNTIME_COMPLETE (final_synthesis.ready + G1 complete), not Canonical Goal-spec
    VERIFIED_SUCCESS (all acceptance items evidenced).
    """
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("answer"))
    result = run_chat_turn(empty_session("c1-runtime-complete"), "file audit", chat_fn=chat, model="fake")
    assert execution_stop_reason_from_result(result) == LoopStopReason.COMPLETED.value
    runtime = result["task_runtime"]
    g1 = next(row for row in runtime["goals"] if row["goal_id"] == "G1")
    assert g1["status"] == "complete"
    assert result["final_synthesis"]["ready"] is True
    assert len(result.get("tools") or []) == 1


def test_completion_contract_llm_final_claim_without_runtime_not_completed(
    tmp_path, monkeypatch
):
    """Completion Contract C2/C4: 「完成しました」でも RUNTIME_COMPLETE 未成立なら COMPLETED 禁止."""
    _prepare(monkeypatch, tmp_path)
    session = empty_session("c2-false-success")
    correlation_id = "c2-false-success"
    begin_turn(session["session_id"], correlation_id, correlation_id)
    orchestrator = ChatTaskOrchestrator(correlation_id, "repository audit plan")
    orchestrator.initialize()
    result = _chat_turn(
        "repository audit plan",
        session,
        chat_fn=_chat_sequence(_response("完成しました。作業は完了です。")),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )
    assert execution_stop_reason_from_result(result) == LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK.value
    g1 = next(
        row for row in result["task_runtime"]["goals"] if row["goal_id"] == "G1"
    )
    assert g1["status"] != "complete"
    assert result.get("final_synthesis", {}).get("ready") is not True


def test_completion_contract_partial_open_tasks_not_completed(tmp_path, monkeypatch):
    """Completion Contract C3: open tasks remain → RUNTIME_COMPLETE 未成立 → not COMPLETED."""
    _prepare(monkeypatch, tmp_path)
    session = empty_session("c3-partial")
    correlation_id = "c3-partial"
    begin_turn(session["session_id"], correlation_id, correlation_id)
    orchestrator = ChatTaskOrchestrator(correlation_id, "repository audit plan")
    orchestrator.initialize()
    result = _chat_turn(
        "repository audit plan",
        session,
        chat_fn=_chat_sequence(_response("interim summary; observation still in progress")),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )
    tasks = {row["task_id"]: row for row in result["task_runtime"]["tasks"]}
    assert tasks["T1"]["status"] != "complete"
    assert tasks["T2"]["status"] != "complete"
    g1 = next(row for row in result["task_runtime"]["goals"] if row["goal_id"] == "G1")
    assert g1["status"] != "complete"
    assert execution_stop_reason_from_result(result) != LoopStopReason.COMPLETED.value


def test_timing_breakdown_separates_initial_tool_and_post_tool(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success", "data": {"x": 1}})
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file")]), _response("answer")
    )
    result = run_chat_turn(
        empty_session("timing-phases"), "file audit", chat_fn=chat, model="fake"
    )
    timing = result["timing_breakdown"]
    assert timing["total_turn_ms"] >= sum(
        timing[key]
        for key in (
            "agent_initial_llm_ms",
            "tool_execution_ms",
            "agent_post_tool_llm_ms",
        )
    )
    assert [row["phase"] for row in timing["llm_calls"]] == [
        "agent_initial_llm",
        "agent_post_tool_llm",
    ]
    assert result["task_runtime"]["timing"] == timing


def test_requirement_llm_has_its_own_timing_phase(tmp_path, monkeypatch):
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.delenv("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", raising=False)
    span_json = json.dumps(
        {
            "disposition": "GOAL",
            "constraint_subtype": None,
            "materiality": "blocks_design",
            "unknown_kind": None,
            "normalized_meaning": "repository audit",
            "resolution_status": "resolved",
        },
        ensure_ascii=False,
    )
    result = run_chat_turn(
        empty_session("requirement-timing"),
        "repository audit",
        chat_fn=_chat_sequence(_response(span_json), _response("answer")),
        model="fake",
    )
    calls = result["timing_breakdown"]["llm_calls"]
    assert [row["phase"] for row in calls] == [
        "requirement_resolution",
        "agent_initial_llm",
    ]
    assert all(row["request_started_at"] for row in calls)
    assert all(row["request_finished_at"] for row in calls)


def test_25_real_loop_emits_major_activity_states(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("answer"))
    result = run_chat_turn(empty_session("events"), "file audit", chat_fn=chat, model="fake")
    states = [event.get("status") for event in result["events"] if event.get("type") == "activity"]
    assert "LLM_WAITING" in states
    assert "TOOL_RUNNING" in states
    assert "RESULT_AUDITING" in states
    assert "COMPLETION_CHECKING" in states
    assert "FINAL_SYNTHESIS" in states


def test_26_late_cancelled_response_is_not_answer_or_evidence(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("late")

    def chat(**_kwargs):
        active = snapshot_activity("late")
        request_cancel("late", str(active["turn_id"]))
        return _response("late answer")

    result = run_chat_turn(session, "repository audit", chat_fn=chat, model="fake")
    assert result["cancelled"]
    assert result["answer"]
    assert "late answer" not in result["answer"]
    assert result["runtime_status_report"]["reason_code"] == "USER_CANCELLED"
    assert result["task_runtime"]["evidence"] == []


def test_27_failure_does_not_mark_task_failed(tmp_path, monkeypatch):
    _prepare(
        monkeypatch,
        tmp_path,
        {"ok": False, "status": "failure", "error": {"code": "path_not_found", "message": "x"}},
    )
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("fallback"))
    result = run_chat_turn(empty_session("failure"), "file audit", chat_fn=chat, model="fake")
    assert result["task_runtime"]["tasks"][0]["status"] == "in_progress"


def test_28_tool_arguments_are_absent_from_public_activity(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    secret = "C:/Users/private/secret.txt"
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file", {"path": secret})]), _response("answer")
    )
    result = run_chat_turn(empty_session("safe-ui"), "file audit", chat_fn=chat, model="fake")
    activity = [event for event in result["events"] if event.get("type") == "activity"]
    assert secret not in str(activity)


def test_29_task_runtime_records_required_execution_events(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    chat = _chat_sequence(_response(calls=[_tool_call("read_file")]), _response("answer"))
    result = run_chat_turn(empty_session("task-events"), "file audit", chat_fn=chat, model="fake")
    types = {row["type"] for row in result["task_runtime"]["events"]}
    assert {
        "GOAL_CREATED",
        "GOAL_DECOMPOSED",
        "TASK_CREATED",
        "TASK_STARTED",
        "ACTION_STARTED",
        "ACTION_COMPLETED",
        "EVIDENCE_ADDED",
        "TASK_COMPLETED",
        "GOAL_COMPLETED",
        "FINAL_SYNTHESIS",
    } <= types


def test_30_session_activity_exposes_in_flight_heartbeat():
    session = empty_session("activity-api")
    begin_turn("activity-api", "turn", "correlation", clock=lambda: 0)
    update_activity(
        "activity-api", "turn", ActivityStatus.LLM_WAITING, clock=lambda: 1
    )
    active = session_activity(session)["active_turn"]
    assert active["status"] == "LONG_RUNNING"
    assert "長時間" in active["message"]


def test_31_missing_required_capability_creates_tool_gap_candidate():
    orchestrator = ChatTaskOrchestrator("turn", "ファイルを読んで")
    orchestrator.initialize()
    gap = orchestrator.detect_required_tool_gap([])
    assert gap is not None
    assert gap.required_capability == "workspace_file_read"


def test_32_existing_required_capability_avoids_tool_gap():
    orchestrator = ChatTaskOrchestrator("turn", "ファイルを読んで")
    orchestrator.initialize()
    assert orchestrator.detect_required_tool_gap(
        [{"name": "read_file", "description": "read_file"}]
    ) is None


def test_33_tool_round_limit_waits_for_explicit_final_response(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    responses = [
        _response(calls=[_tool_call("list_files", {"path": f"p{index}"})])
        for index in range(5)
    ]
    responses.append(_response("final answer after tools"))
    result = run_chat_turn(
        empty_session("final-wait"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    lifecycle = result["final_llm_lifecycle"]
    assert result["answer"] == "final answer after tools"
    assert lifecycle["final_llm_response_received"]
    assert lifecycle["final_response_accepted"]
    assert lifecycle["final_llm_response_length"] == 24


def test_34_real_model_empty_is_distinguished_from_missing_response(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    result = run_chat_turn(
        empty_session("model-empty"),
        "file audit",
        chat_fn=_chat_sequence(_response("")),
        model="fake",
    )
    lifecycle = result["final_llm_lifecycle"]
    assert lifecycle["final_llm_response_received"]
    assert lifecycle["empty_reason"] == "MODEL_RETURNED_EMPTY"
    assert not lifecycle["turn_closed_before_response"]
    assert result["answer"]
    assert result["runtime_status_report"]["reason_code"] == "LLM_EMPTY_RESPONSE"


def test_35_finalization_occurs_after_response_receipt(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    result = run_chat_turn(
        empty_session("final-order"),
        "file audit",
        chat_fn=_chat_sequence(_response("answer")),
        model="fake",
    )
    lifecycle = result["final_llm_lifecycle"]
    assert lifecycle["final_llm_response_received_at"] <= lifecycle["turn_finalization_started_at"]
    assert lifecycle["turn_finalization_started_at"] <= lifecycle["turn_finalization_finished_at"]


def test_36_late_final_response_is_recorded_and_discarded(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("late-lifecycle")

    def chat(**_kwargs):
        active = snapshot_activity("late-lifecycle")
        request_cancel("late-lifecycle", str(active["turn_id"]))
        return _response("late final")

    result = run_chat_turn(session, "file audit", chat_fn=chat, model="fake")
    lifecycle = result["final_llm_lifecycle"]
    assert result["answer"]
    assert "late final" not in result["answer"]
    assert lifecycle["late_response_received"]
    assert lifecycle["final_response_discarded"]
    assert lifecycle["empty_reason"] == "RESPONSE_DISCARDED"


def test_37_progress_does_not_consume_stagnation_budget():
    counters = LoopCounters(
        stagnation_limit=3,
        same_failure_limit=3,
        no_evidence_limit=6,
        configured_tool_limit=20,
    )
    counters.observe(signature="read:a", status="success", evidence_gain=True)
    counters.observe(signature="read:b", status="success", evidence_gain=False)
    assert counters.total_tool_calls == 2
    assert counters.stagnation_count == 0
    assert counters.no_evidence_count == 1
    assert counters.stop_reason() is None


def test_38_same_failed_action_has_separate_counter():
    counters = LoopCounters(
        stagnation_limit=5,
        same_failure_limit=2,
        no_evidence_limit=6,
        configured_tool_limit=20,
    )
    counters.observe(signature="read:missing", status="failure", evidence_gain=False)
    counters.observe(signature="read:missing", status="failure", evidence_gain=False)
    assert counters.same_failure_count == 2
    assert counters.stop_reason() is LoopStopReason.SAME_FAILURE_LIMIT


def test_38b_no_evidence_and_stagnation_are_independent():
    counters = LoopCounters(
        stagnation_limit=2,
        same_failure_limit=9,
        no_evidence_limit=4,
        configured_tool_limit=20,
    )
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    assert counters.stagnation_count == 1
    assert counters.no_evidence_count == 2
    assert counters.stop_reason() is None
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    assert counters.stop_reason() is LoopStopReason.STAGNATION_LIMIT


def test_38c_different_action_without_evidence_does_not_reset_stagnation():
    counters = LoopCounters(
        stagnation_limit=5,
        same_failure_limit=9,
        no_evidence_limit=6,
        configured_tool_limit=20,
    )
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    counters.observe(signature="read:a", status="success", evidence_gain=False)
    assert counters.stagnation_count == 1
    counters.observe(signature="search:b", status="success", evidence_gain=False)
    assert counters.stagnation_count == 1
    assert counters.no_evidence_count == 3


def test_38d_same_information_via_different_tool_is_not_new_evidence():
    orchestrator = ChatTaskOrchestrator("turn", "file audit")
    orchestrator.initialize()
    summary = {"fact": "same"}
    orchestrator.observe_tool(
        "read_file",
        {"path": "a"},
        {"status": "success"},
        summary,
        relevant_tools=["read_file", "search_files"],
    )
    orchestrator.observe_tool(
        "search_files",
        {"query": "b"},
        {"status": "success"},
        summary,
        relevant_tools=["read_file", "search_files"],
    )
    assert len(orchestrator.runtime.evidence) == 1
    assert orchestrator.runtime.actions[-1].evidence_gain is False


def test_39_stagnation_stop_returns_status_without_completing_task(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_stagnation_limit": 2,
            "agent_same_failure_limit": 3,
            "agent_no_evidence_limit": 6,
            "semantic_stagnation_warning_enabled": False,
        },
    )
    responses = [
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(calls=[_tool_call("read_file", {"path": "same.md"})]),
        _response(""),
    ]
    result = run_chat_turn(
        empty_session("stagnation-stop"),
        "file audit",
        chat_fn=_chat_sequence(*responses),
        model="fake",
    )
    report = result["runtime_status_report"]
    assert report["reason_code"] == "STAGNATION_LIMIT"
    assert result["loop_counters"]["total_tool_calls"] == 3
    assert result["answer"]
    assert result.get("final_synthesis") is None or result["final_synthesis"]["ready"] is False
    assert result.get("system_fast_exit") is True
    assert result.get("gap_resolution") is None
    assert result["task_runtime"]["goals"][0]["status"] != "complete"
    assert snapshot_activity("stagnation-stop")["status"] == "BLOCKED"


def test_40_timeout_has_status_report_and_is_not_completed(tmp_path, monkeypatch):
    _prepare(monkeypatch, tmp_path)

    def timeout(**_kwargs):
        raise TimeoutError("LLM timed out")

    result = run_chat_turn(
        empty_session("timeout-status"),
        "file audit",
        chat_fn=timeout,
        model="fake",
    )
    assert result["answer"]
    assert "TIMEOUT" in result["answer"]
    assert result["runtime_status_report"]["reason_code"] == "TIMEOUT"
    assert result["runtime_status_report"]["status"] == "IN_PROGRESS"
    assert snapshot_activity("timeout-status")["status"] == "BLOCKED"


_COVERAGE_REQUEST = """Completion Condition:
1. 必須Envelope fieldを取得する
2. statusの許可値を取得する
3. successの成立条件を取得する
4. partialの成立条件を取得する
5. failureの成立条件を取得する
"""


def test_41_explicit_completion_conditions_are_tracked_individually():
    orchestrator = ChatTaskOrchestrator("coverage", _COVERAGE_REQUEST)
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    assert len(task.completion_conditions) == 5
    assert set(task.condition_status.values()) == {"UNKNOWN"}


def test_42_partial_coverage_stays_in_progress_with_evidence_mapping():
    orchestrator = ChatTaskOrchestrator("coverage", _COVERAGE_REQUEST)
    orchestrator.initialize()
    raw = {
        "lines": [
            {"line": 1, "text": "## 基本Envelope"},
            {"line": 2, "text": "必須field: `ok`, `status`, `error`, `warnings`"},
        ]
    }
    orchestrator.observe_tool(
        "read_file", {"path": "contract.md"}, {"status": "success"}, {},
        relevant_tools=["read_file"], raw_result=raw,
    )
    task = orchestrator.runtime.tasks["T1"]
    assert task.status == "in_progress"
    assert list(task.condition_status.values()).count("SATISFIED") == 1
    assert task.condition_evidence[task.completion_conditions[0]] == ["E1"]
    assert orchestrator.current_task_id == "T1"
    synthesis = orchestrator.finish("an answer")
    assert synthesis["ready"] is False
    assert orchestrator.runtime.tasks["T2"].status == "pending"


def test_43_all_covered_conditions_complete_observation_task():
    orchestrator = ChatTaskOrchestrator("coverage", _COVERAGE_REQUEST)
    orchestrator.initialize()
    content = """必須field: `ok`, `status`, `error`, `warnings`
status: `success`, `partial`, `failure`
### success
complete result
### partial
incomplete result
### failure
no usable result
"""
    raw = {"lines": [{"line": i, "text": line} for i, line in enumerate(content.splitlines(), 1)]}
    orchestrator.observe_tool(
        "read_file", {"path": "contract.md"}, {"status": "success"}, {},
        relevant_tools=["read_file"], raw_result=raw,
    )
    task = orchestrator.runtime.tasks["T1"]
    assert task.status == "complete"
    assert set(task.condition_status.values()) == {"SATISFIED"}
    assert all(refs == ["E1"] for refs in task.condition_evidence.values())
    evidence = orchestrator.runtime.evidence["E1"]
    assert evidence.tool_name == "read_file"
    assert evidence.target == "contract.md"
    assert len(evidence.supported_completion_conditions) == 5


def test_44_non_ready_requirement_stops_before_agent_execution(tmp_path, monkeypatch):
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [RequirementCondition("C1", "対象ファイルを読む", ambiguity="missing_input")],
            "MISSING_INPUT",
            clarification="対象ファイルのパスを指定してください。",
        ),
    )

    def unexpected_chat(**_kwargs):
        raise AssertionError("task execution must not start")

    result = run_chat_turn(
        empty_session("requirements-missing"),
        "対象を調査して報告してください",
        chat_fn=unexpected_chat,
        model="fake",
    )
    assert result["answer"] == "対象ファイルのパスを指定してください。"
    assert result["requirement_decomposition"]["status"] == "MISSING_INPUT"
    assert result["task_runtime"] is None


def test_45_ready_requirements_are_registered_in_completion_coverage():
    conditions = ["必須fieldを取得する", "statusの許可値を取得する"]
    orchestrator = ChatTaskOrchestrator(
        "requirements-ready", "契約を調査する", completion_conditions=conditions
    )
    orchestrator.initialize()
    task = orchestrator.runtime.tasks["T1"]
    assert task.completion_conditions == conditions
    assert task.condition_status == {condition: "UNKNOWN" for condition in conditions}
    assert task.status == "pending"


def test_46_known_workspace_path_builds_required_read_expectation():
    tools = [{"type": "function", "function": {"name": "read_file"}}]
    expectation = build_tool_expectation(
        "docs/TOOL_RESULT_CONTRACT.md を実際に確認してください", tools
    )
    assert expectation.generated is True
    assert expectation.required_capability == "workspace_file_read"
    assert expectation.expected_tool == "read_file"
    from ai_tool.chat_interface.workspace_read_bridge import runtime_initial_read_arguments

    assert expectation.expected_arguments == runtime_initial_read_arguments(
        "docs/TOOL_RESULT_CONTRACT.md"
    )
    assert expectation.level == "required"


def test_47_ambiguous_request_does_not_force_a_tool():
    tools = [{"type": "function", "function": {"name": "read_file"}}]
    expectation = build_tool_expectation("仕様を適切に確認してください", tools)
    assert expectation.generated is False
    assert expectation.level == "none"


def test_h4_1_expectation_not_generated_when_help_tool_absent_from_tools():
    tools = [{"type": "function", "function": {"name": "search_web"}}]
    expectation = build_tool_expectation(
        "docs/TOOL_RESULT_CONTRACT.md を実際に確認してください", tools
    )
    assert expectation.generated is False
    assert expectation.level == "none"


def test_h4_1_web_gpu_cpu_required_capability_uses_index_ids():
    from ai_tool.chat_interface.capability_resolution import required_capabilities

    web = ChatTaskOrchestrator("turn", "web の情報を調べる")
    web.initialize()
    assert web.required_capability() == "web_search"
    gpu = ChatTaskOrchestrator("turn", "gpu の状態を確認する")
    gpu.initialize()
    assert "gpu_device_observation" in required_capabilities(gpu.task)
    assert "cpu_observation" not in required_capabilities(gpu.task)
    cpu = ChatTaskOrchestrator("turn", "CPU を見て")
    cpu.initialize()
    assert cpu.required_capability() == "cpu_observation"


def test_48_expectation_hint_and_actual_match_are_recorded():
    tools = [{"type": "function", "function": {"name": "read_file"}}]
    orchestrator = ChatTaskOrchestrator(
        "expectation", "docs/TOOL_RESULT_CONTRACT.md を実際に確認してください"
    )
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(tools)
    assert "Tool Expectation:" in orchestrator.hint()
    orchestrator.observe_tool(
        "read_file",
        {"path": "docs/TOOL_RESULT_CONTRACT.md"},
        {"status": "success"},
        {},
        relevant_tools=["read_file"],
        raw_result={"content": "contract"},
    )
    recorded = orchestrator.snapshot()["tool_expectation"]
    assert recorded["actual_tool_called"] == "read_file"
    assert recorded["expectation_matched"] is True
