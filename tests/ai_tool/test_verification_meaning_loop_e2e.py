from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.chat_session import load_session, save_session
from ai_tool.production_verification_acceptance import TEST_RUN_CLOSED
from ai_tool.verification_only_execution import (
    execute_verification_only_reentry as execute_verification_only_reentry_real,
)
from tests.ai_tool.verification_meaning_loop_fixture import (
    build_verification_meaning_loop_fixture,
)
from tools.ai.task_runtime import ActionRecord, EvidenceRecord


def test_verification_only_evidence_uses_run_test_plan_condition_contract(
    tmp_path, monkeypatch
):
    import ai_tool.chat_interface.chat_session as sessions

    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    fixture = build_verification_meaning_loop_fixture(tmp_path)
    session = fixture["session"]
    initial_contract = session["production_run_contract"]
    initial_sandbox_id = fixture["sandbox"].session_id
    calls = {"count": 0}

    def execute_action(orchestrator, runtime_task_id, arguments):
        calls["count"] += 1
        runtime = orchestrator.runtime
        task = runtime.tasks[runtime_task_id]
        action_id = "A6"
        evidence_id = "E6"
        runtime.record_verification_action(
            ActionRecord(
                action_id,
                runtime_task_id,
                "tool_call",
                "run_test_plan",
                dict(arguments),
                "success",
                evidence_gain=True,
            )
        )
        runtime.add_evidence(
            EvidenceRecord(
                evidence_id,
                "test_safety_run",
                "test_safety://A6",
                "verification succeeded",
                action_id,
                tool_name="run_test_plan",
                supported_completion_conditions=[TEST_RUN_CLOSED],
            ),
            [runtime_task_id],
        )
        runtime.support_completion_conditions(
            runtime_task_id, evidence_id, [TEST_RUN_CLOSED]
        )
        return {"status": "success"}

    def injected_adapter(orchestrator, reentry):
        return execute_verification_only_reentry_real(
            orchestrator, reentry, execute_action=execute_action
        )

    mission_store = SimpleNamespace(
        get_mission=lambda mission_id: (
            fixture["mission"]
            if mission_id == fixture["mission"]["mission_id"]
            else None
        )
    )
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn.MissionMemoryStore.from_default",
        lambda: mission_store,
    )
    monkeypatch.setattr(
        "ai_tool.verification_only_execution.execute_verification_only_reentry",
        injected_adapter,
    )

    finalization_calls = []

    def finalization_chat(**kwargs):
        finalization_calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content="Verification evidence has been refreshed.")
        )

    result = run_chat_turn(
        session,
        "/run",
        model="test",
        chat_fn=finalization_chat,
    )

    snapshot = session["production_runtime_snapshot"]
    tasks = {row["task_id"]: row for row in snapshot["tasks"]}
    evidence_ids = {row["evidence_id"] for row in snapshot["evidence"]}
    criterion = session["production_acceptance_evaluation"]["result"]["criterion_trace"][0]

    assert result["verification_execution"]["status"] == "VERIFICATION_EXECUTED"
    assert calls["count"] == 1
    assert {"E5", "E6"} <= evidence_ids
    assert tasks["gh-T1"]["status"] == "complete"
    assert tasks["gh-T1"]["condition_evidence"][TEST_RUN_CLOSED] == ["E6"]
    assert criterion["evidence_requirement_trace"]["coverage"] == "MATCH"
    assert session["production_acceptance_evaluation"]["result"]["status"] == "PASS"
    assert session["production_goal_acceptance_judgment"]["completion_eligibility"]["completion_eligible"] is True
    assert session["production_goal_acceptance_judgment"]["goal_completed"] is True
    assert result["production_status"] == "GOAL_ACCEPTANCE_JUDGED"
    assert len(finalization_calls) == 1
    assert finalization_calls[0]["tools"] == []
    assert session["production_run_contract"] == initial_contract
    assert snapshot["sandbox_session"]["session_id"] == initial_sandbox_id

    save_session(session)
    reloaded = load_session(session["session_id"])
    assert reloaded["production_run_contract"] == initial_contract
    assert (
        reloaded["production_runtime_snapshot"]["sandbox_session"]["session_id"]
        == initial_sandbox_id
    )

    def unexpected_finalization(**_kwargs):
        raise AssertionError("completed Goal must not run finalization again")

    second = run_chat_turn(
        reloaded,
        "/run",
        model="test",
        chat_fn=unexpected_finalization,
    )

    assert calls["count"] == 1
    assert len(finalization_calls) == 1
    assert second["production_status"] == "GOAL_ACCEPTANCE_JUDGED"
    assert second["acceptance_reused"] is True
    assert second["goal_judgment_reused"] is True
    assert "verification_execution" not in second
    assert reloaded["production_run_contract"] == initial_contract
    assert (
        reloaded["production_runtime_snapshot"]["sandbox_session"]["session_id"]
        == initial_sandbox_id
    )
    assert {row["evidence_id"] for row in reloaded["production_runtime_snapshot"]["evidence"]} >= {
        "E5",
        "E6",
    }
