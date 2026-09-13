"""Parametrized cross-cutting invariants for Execution end branches.

Visualizes which branches violate anti-silent-end / next-action contracts today.
Does not implement needs_continuation or other production fixes.
"""
from __future__ import annotations

import pytest

from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.chat_interface.activity_status import begin_turn, request_cancel, snapshot_activity
from ai_tool.chat_interface.agent_turn import _chat_turn, run_chat_turn
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.chat_interface.chat_session import empty_session
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementCondition,
    RequirementDecomposition,
    RequirementStatus,
)
from tools.ai.task_runtime import EvidenceRecord, InformationCertainty
from tests.ai_tool.chat_interface.execution_end_invariants import (
    EndBranchContract,
    FieldContract,
    ScenarioRun,
    collect_failures,
    evaluate_execution_end_invariants,
    execution_stop_reason_from_result,
    format_invariant_report,
)
from tests.ai_tool.chat_interface.test_agent_task_loop_p216 import (
    _chat_sequence,
    _prepare,
    _prepare_paths_only,
    _response,
    _tool_call,
)
from tests.ai_tool.chat_interface.test_goal_completion_gate import (
    ABSENCE_COMPLETES_REPLY,
    README_E2E_REQUEST,
    ROOT_WITHOUT_NAMED_FILE,
    _listing_execute,
)
from tests.ai_tool.chat_interface.test_h4_selection_core import _observe_root_listing

REGISTRY = load_registry_tools()

# agent_turn does not assign LoopStopReason.TOOL_HARD_LIMIT (counter limit wiring gap).
KNOWN_PREEXISTING_INVARIANT_BRANCH_FAILURES = frozenset({"tool_hard_limit"})


def _run_simple_chat(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("inv-simple")
    result = run_chat_turn(
        session,
        "こんにちは",
        chat_fn=_chat_sequence(_response("hello")),
        model="fake",
    )
    return result, session


def _run_agent_false_success_llm_final_without_runtime(monkeypatch, tmp_path):
    """One tool + LLM final text; runtime G1 is not canonically complete (false success regression)."""
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    session = empty_session("inv-false-success")
    correlation_id = "inv-false-success"
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "repository audit plan"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file", {"path": "a.txt"})]),
        _response("audit summary without verified evidence"),
    )
    result = _chat_turn(
        request,
        session,
        chat_fn=chat,
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )
    resume = result.get("goal_continuation_resume")
    session["awaiting_goal_continuation"] = bool(resume)
    session["goal_continuation_resume"] = resume
    return result, session


def _run_goal_completion_human(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("inv-gc-human")
    result = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    return result, session


def _run_goal_completion_judged(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("inv-gc-judged")
    first = run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    assert first.get("awaiting_goal_completion_human")
    second = run_chat_turn(
        session,
        ABSENCE_COMPLETES_REPLY,
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    return second, session


def _run_goal_completion_ended_incomplete(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("inv-gc-incomplete")
    run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    result = run_chat_turn(
        session,
        "2",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    return result, session


def _run_goal_completion_unsupported(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._execute_agent_tool",
        _listing_execute(),
    )
    session = empty_session("inv-gc-unsupported")
    run_chat_turn(
        session,
        README_E2E_REQUEST,
        chat_fn=_chat_sequence(
            _response(calls=[_tool_call("list_files", {"path": "."})]),
            _response("README.md は存在しません"),
        ),
        model="fake",
    )
    result = run_chat_turn(
        session,
        "ほかの場所も探してください",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    return result, session


def _run_human_grill_stop(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    session = empty_session("inv-grill-stop")
    correlation_id = "inv-grill-stop"
    begin_turn(session["session_id"], correlation_id, correlation_id)
    request = "gridを検索して、その内容を要約してほしい。"
    orchestrator = ChatTaskOrchestrator(correlation_id, request)
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)

    def execute(name, arguments, **_kwargs):
        if name != "search_files":
            raise AssertionError(name)
        return {
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    responses = iter(
        [
            _response(calls=[_tool_call("search_files", {"query": "grid", "path": "."})]),
            _response("候補が複数あります。"),
            _response("候補が複数あります。"),
        ]
    )
    result = _chat_turn(
        request,
        session,
        chat_fn=lambda **_kwargs: next(responses),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )
    return result, session


def _run_human_grill_resume(monkeypatch, tmp_path):
    request = "gridを検索して、その内容を要約してほしい。"
    first = ChatTaskOrchestrator("grill-resume", request)
    first.initialize()
    first.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    first.observe_tool(
        "search_files",
        {"query": "grid", "path": "."},
        {"ok": True, "status": "success", "error": None, "warnings": []},
        {"query": "grid", "hit_count": 2},
        relevant_tools=["search_files"],
        raw_result={
            "ok": True,
            "status": "success",
            "query": "grid",
            "matches": [
                {"path": "AGENTS.md", "line": 1, "text": "grid"},
                {"path": "docs/CURRENT_DEVELOPMENT_STATE.md", "line": 2, "text": "grid"},
            ],
            "has_more": False,
            "next_cursor": None,
            "error": None,
            "warnings": [],
        },
    )
    session = empty_session("inv-grill-resume")
    session["awaiting_human_grill"] = True
    session["conversation_grill_state"] = first.conversation_grill_state()
    path = "docs/CURRENT_DEVELOPMENT_STATE.md"

    def execute(name, arguments, **_kwargs):
        assert name == "read_file"
        return {
            "ok": True,
            "status": "success",
            "lines": [{"line": 1, "text": "# Current Development State"}],
            "error": None,
            "warnings": [],
        }

    monkeypatch.setattr("ai_tool.chat_interface.agent_turn._execute_agent_tool", execute)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.chat_trust_path",
        lambda _sid: tmp_path / "trust.json",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.chat_session.SESSIONS_DIR",
        tmp_path / "sessions",
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [RequirementCondition("C1", "relevant evidence observed")], "READY"
        ),
    )
    result = run_chat_turn(
        session,
        path,
        chat_fn=_chat_sequence(_response("要約です。")),
        model="fake",
    )
    return result, session


def _run_tool_hard_limit(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, {"ok": True, "status": "success"})
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.get_pipeline",
        lambda: {
            "max_tool_rounds": 1,
            "agent_tool_absolute_hard_limit": 2,
            "agent_stagnation_limit": 3,
            "agent_same_failure_limit": 3,
            "agent_no_evidence_limit": 6,
        },
    )
    session = empty_session("inv-hard-limit")
    chat = _chat_sequence(
        _response(calls=[_tool_call("read_file", {"path": "a"})]),
        _response(calls=[_tool_call("read_file", {"path": "b"})]),
        _response(""),
    )
    result = run_chat_turn(session, "repository audit plan", chat_fn=chat, model="fake")
    return result, session


def _run_runtime_error(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)

    def boom(**_kwargs):
        raise RuntimeError("provider down")

    session = empty_session("inv-runtime-error")
    result = run_chat_turn(session, "repository audit plan", chat_fn=boom, model="fake")
    return result, session


def _run_llm_empty(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("inv-llm-empty")
    result = run_chat_turn(
        session,
        "repository audit plan",
        chat_fn=_chat_sequence(_response("")),
        model="fake",
    )
    return result, session


def _run_user_cancelled(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("inv-cancelled")

    def chat(**_kwargs):
        active = snapshot_activity("inv-cancelled")
        request_cancel("inv-cancelled", str(active["turn_id"]))
        return _response("late answer")

    result = run_chat_turn(session, "repository audit plan", chat_fn=chat, model="fake")
    return result, session


def _run_timeout(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)

    def timeout(**_kwargs):
        raise TimeoutError("LLM timed out")

    session = empty_session("inv-timeout")
    result = run_chat_turn(session, "repository audit plan", chat_fn=timeout, model="fake")
    return result, session


def _run_requirement_blocked(monkeypatch, tmp_path):
    _prepare_paths_only(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.decompose_requirements",
        lambda *_args, **_kwargs: RequirementDecomposition(
            [],
            RequirementStatus.MISSING_INPUT.value,
            clarification="完了条件を確認してください。",
        ),
    )
    session = empty_session("inv-req-blocked")
    result = run_chat_turn(
        session,
        "repository audit plan",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    return result, session


def _run_help(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("inv-help")
    result = run_chat_turn(
        session,
        "/h",
        chat_fn=_chat_sequence(_response("unused")),
        model="fake",
    )
    return result, session


def _run_approval_required(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)
    session = empty_session("inv-approval")
    correlation_id = "inv-approval"
    begin_turn(session["session_id"], correlation_id, correlation_id)
    orchestrator = ChatTaskOrchestrator(correlation_id, "repository audit plan")
    orchestrator.initialize()
    orchestrator.configure_tool_expectation(REGISTRY, registry_tools=REGISTRY)
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1",
            source_type="capability_registry_check",
            source="registry/tools.json",
            summary="no edit tool",
            created_by_action="A1",
            relevant_content="",
            certainty=InformationCertainty.CONFIRMED.value,
            verified=True,
            created_at="t",
        ),
        ["T1"],
    )
    orchestrator.runtime.record_confirmed_tool_gap(
        "T1",
        "workspace_file_edit",
        registry_checked=True,
        capability_index_checked=True,
        existing_candidates=[],
        rejected_candidates=[],
        suggested_minimal_tool="edit_file",
        evidence_ids=["E1"],
    )
    result = _chat_turn(
        "repository audit plan",
        session,
        chat_fn=_chat_sequence(_response("cannot edit without approval")),
        model="fake",
        memory={},
        correlation_id=correlation_id,
        orchestrator=orchestrator,
    )
    return result, session


SCENARIOS: list[ScenarioRun] = [
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="simple_chat",
            spec_source="test_mission_memory_chat_write.py (no mission for simple chat)",
            entry="run_chat_turn",
            mission_persist=FieldContract.NOT_CONNECTED,
            next_action_or_terminal=FieldContract.UNDECIDED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_simple_chat,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="agent_false_success_llm_final_without_runtime",
            spec_source=(
                "Completion Contract v0: LLM final alone must not yield COMPLETED "
                "when TaskRuntime / final_synthesis.ready are incomplete"
            ),
            entry="run_chat_turn",
            expected_stop_reason="GOAL_INCOMPLETE_OPEN_WORK",
            expected_judgment="not_judged",
            expected_goal_achievement_performed=False,
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
            notes="Former agent_completed_normal; old COMPLETED was false success",
        ),
        run=_run_agent_false_success_llm_final_without_runtime,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="goal_completion_human",
            spec_source="GOAL_COMPLETION_GATE_V0.md §13",
            entry="run_chat_turn",
            expected_stop_reason="GOAL_COMPLETION_HUMAN",
            expected_judgment="not_judged",
            expected_goal_achievement_performed=False,
            next_action_or_terminal=FieldContract.REQUIRED,
            resume=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_goal_completion_human,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="goal_completion_judged_achieved",
            spec_source="GOAL_COMPLETION_GATE_V0.md §13 resume → achieved",
            entry="run_chat_turn (human resume)",
            expected_stop_reason="GOAL_COMPLETION_JUDGED",
            expected_judgment="judged",
            expected_end_state="achieved",
            expected_goal_achievement_performed=True,
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_goal_completion_judged,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="goal_completion_judged_ended_incomplete",
            spec_source="goal_completion_gate.interpret_goal_completion_answer (option 2)",
            entry="run_chat_turn (human resume)",
            expected_stop_reason="GOAL_COMPLETION_JUDGED",
            expected_judgment="judged",
            expected_end_state="ended_incomplete",
            expected_goal_achievement_performed=True,
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_goal_completion_ended_incomplete,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="goal_completion_unsupported",
            spec_source="GOAL_COMPLETION_GATE_V0.md §13 unsupported stop",
            entry="run_chat_turn (human resume)",
            expected_stop_reason="GOAL_COMPLETION_UNSUPPORTED",
            expected_judgment="not_judged",
            expected_goal_achievement_performed=False,
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_goal_completion_unsupported,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="human_grill_stop",
            spec_source="agent_turn._runtime_status_report HUMAN_GRILL",
            entry="_chat_turn (same agent loop body as run_chat_turn)",
            expected_stop_reason="HUMAN_GRILL",
            expected_judgment="judged",
            expected_end_state="paused",
            next_action_or_terminal=FieldContract.REQUIRED,
            resume=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_human_grill_stop,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="human_grill_resume",
            spec_source="test_agent_loop_connection_recovery_p2181 grill resume",
            entry="run_chat_turn (session.awaiting_human_grill)",
            expected_stop_reason="COMPLETED",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.UNDECIDED,
            anti_silent_end=FieldContract.UNDECIDED,
            notes="Post-grill completion next_action spec UNDECIDED",
        ),
        run=_run_human_grill_resume,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="tool_hard_limit",
            spec_source="agent_turn._runtime_status_report TOOL_HARD_LIMIT",
            entry="run_chat_turn",
            expected_stop_reason="TOOL_HARD_LIMIT",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_tool_hard_limit,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="runtime_error",
            spec_source="test_mission_memory_chat_write undetermined execution",
            entry="run_chat_turn",
            expected_stop_reason="RUNTIME_ERROR",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_runtime_error,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="llm_empty_response",
            spec_source="test_agent_task_loop_p216 test_34",
            entry="run_chat_turn",
            expected_stop_reason="LLM_EMPTY_RESPONSE",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_llm_empty,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="user_cancelled",
            spec_source="test_agent_task_loop_p216 test_26",
            entry="run_chat_turn",
            expected_stop_reason="USER_CANCELLED",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_user_cancelled,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="timeout",
            spec_source="test_agent_task_loop_p216 test_40",
            entry="run_chat_turn",
            expected_stop_reason="TIMEOUT",
            expected_judgment="not_judged",
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_timeout,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="requirement_blocked",
            spec_source="run_chat_turn requirement early return",
            entry="run_chat_turn",
            mission_persist=FieldContract.NOT_CONNECTED,
            next_action_or_terminal=FieldContract.REQUIRED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_requirement_blocked,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="help_h",
            spec_source="run_chat_turn /h intercept",
            entry="run_chat_turn",
            mission_persist=FieldContract.NOT_APPLICABLE,
            next_action_or_terminal=FieldContract.UNDECIDED,
            anti_silent_end=FieldContract.REQUIRED,
        ),
        run=_run_help,
    ),
    ScenarioRun(
        contract=EndBranchContract(
            branch_id="approval_required",
            spec_source="GOAL_COMPLETION_GATE_V0.md §12 Approval resume NOT_CONNECTED",
            entry="_chat_turn",
            mission_persist=FieldContract.UNDECIDED,
            next_action_or_terminal=FieldContract.UNDECIDED,
            resume=FieldContract.NOT_CONNECTED,
            anti_silent_end=FieldContract.UNDECIDED,
            notes=(
                "APPROVAL_REQUIRED end-state trigger in isolated _chat_turn: UNDECIDED. "
                "Observed: manual gap injection does not reach APPROVAL_REQUIRED stop yet."
            ),
        ),
        run=_run_approval_required,
    ),
]


def _unwrap_scenario(item) -> ScenarioRun:
    if isinstance(item, ScenarioRun):
        return item
    return item.values[0]


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=lambda item: _unwrap_scenario(item).contract.branch_id,
)
def test_execution_end_invariant_branch(scenario, monkeypatch, tmp_path):
    scenario = _unwrap_scenario(scenario)
    result, session = scenario.run(monkeypatch, tmp_path)
    checks = evaluate_execution_end_invariants(result, session, scenario.contract)
    failures = collect_failures(checks)
    report = format_invariant_report(scenario.contract, checks)
    if scenario.contract.branch_id in KNOWN_PREEXISTING_INVARIANT_BRANCH_FAILURES:
        assert failures == [
            check
            for check in failures
            if check.field == "execution.stop_reason"
        ], report
        assert len(failures) == 1, report
        assert "expected=TOOL_HARD_LIMIT actual=LLM_EMPTY_RESPONSE" in failures[0].detail
        return
    assert not failures, report


def _scenario_items() -> list[ScenarioRun]:
    return [_unwrap_scenario(entry) for entry in SCENARIOS]


def test_agent_false_success_llm_final_without_runtime_complete(monkeypatch, tmp_path):
    """Completion Contract C2: final LLM text does not imply RUNTIME_COMPLETE without runtime graph."""
    result, _session = _run_agent_false_success_llm_final_without_runtime(monkeypatch, tmp_path)
    assert execution_stop_reason_from_result(result) == "GOAL_INCOMPLETE_OPEN_WORK"
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") == "GOAL_INCOMPLETE_OPEN_WORK"
    assert report.get("next_actions")
    runtime = result.get("task_runtime") or {}
    g1 = next(
        (row for row in (runtime.get("goals") or []) if row.get("goal_id") == "G1"),
        None,
    )
    assert g1 is not None
    assert g1.get("status") != "complete"
    synthesis = result.get("final_synthesis") or {}
    assert synthesis.get("ready") is not True


def test_completion_contract_non_agent_chat_excluded_from_goal_contract(
    monkeypatch, tmp_path
):
    """Completion Contract C6: simple chat must not be classified as Goal incomplete."""
    from ai_tool.tool_calling_capability_bridge import ToolCallingBridgeResult

    _prepare(monkeypatch, tmp_path)

    def fake_bridge(*_args, **_kwargs):
        return ToolCallingBridgeResult(
            required_capabilities=[],
            current_model="fake",
            current_worker_id=None,
            current_model_eligible=True,
            selected_model="fake",
            selected_worker_id=None,
            routing_performed=False,
            routing_reason="test",
            capability_source="test",
            capability_gap=False,
            gap_reason=None,
            bridge_applied=False,
        )

    monkeypatch.setattr(
        "ai_tool.tool_calling_capability_bridge.apply_tool_calling_hard_capability_bridge",
        fake_bridge,
    )
    result, _session = _run_simple_chat(monkeypatch, tmp_path)
    assert result.get("task_runtime") is None
    report = result.get("runtime_status_report") or {}
    assert report.get("reason_code") != "GOAL_INCOMPLETE_OPEN_WORK"


def test_execution_end_invariant_matrix_summary(monkeypatch, tmp_path):
    """Single report of PASS / FAIL / NOT_CONNECTED / UNDECIDED across all branches."""
    rows: list[str] = []
    failing_branches: list[str] = []
    for scenario in _scenario_items():
        result, session = scenario.run(monkeypatch, tmp_path)
        checks = evaluate_execution_end_invariants(result, session, scenario.contract)
        failures = collect_failures(checks)
        status = "FAIL" if failures else "PASS"
        if failures and scenario.contract.branch_id not in (
            KNOWN_PREEXISTING_INVARIANT_BRANCH_FAILURES
        ):
            failing_branches.append(scenario.contract.branch_id)
        summary_parts = []
        for check in checks:
            if check.status in {"FAIL", "NOT_CONNECTED", "UNDECIDED"}:
                summary_parts.append(f"{check.field}={check.status}")
        rows.append(
            f"{status}\t{scenario.contract.branch_id}\t{scenario.contract.entry}\t"
            + (", ".join(summary_parts) if summary_parts else "all_required=PASS")
        )
    matrix = "\n".join(["STATUS\tBRANCH\tENTRY\tNOTES", *rows])
    print("\nEXECUTION END INVARIANT MATRIX:\n" + matrix)
    assert not failing_branches, (
        "Execution end invariant matrix has unexpected FAIL branches.\n" + matrix
    )
