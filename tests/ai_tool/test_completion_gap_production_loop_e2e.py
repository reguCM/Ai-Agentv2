from __future__ import annotations

from types import SimpleNamespace

from ai_tool.chat_interface.agent_turn import run_chat_turn
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import restore_orchestrator_from_runtime_snapshot
from ai_tool.production_meaning_context import build_meaning_context_v0
from ai_tool.production_verification_acceptance import TEST_RUN_CLOSED
from tests.ai_tool.verification_meaning_loop_fixture import (
    build_verification_meaning_loop_fixture,
)
from tools.ai.task_runtime import ActionRecord, EvidenceRecord


def test_completion_gap_task_runs_through_production_run_and_closes_goal(tmp_path, monkeypatch) -> None:
    fixture = build_verification_meaning_loop_fixture(tmp_path)
    session = fixture["session"]
    session["production_meaning_context"] = build_meaning_context_v0(
        fixture["mission"], fixture["handoff_packet"]
    )
    acceptance = session["production_acceptance_evaluation"]["result"]
    acceptance["status"] = "FAIL"
    acceptance["criterion_trace"][0]["evidence_requirement_trace"]["coverage"] = "MATCH"
    acceptance["meaning_trace_audit"]["criteria"][0]["meaning_coverage"] = "MATCH"
    session["production_acceptance_readiness"] = {
        "acceptance_ready": True,
        "incomplete_task_ids": [],
        "unresolved_failure_ids": [],
        "missing_evidence": [],
    }
    session["production_goal_acceptance_judgment"].update(
        {"goal_completed": False, "completion_eligibility": {"completion_eligible": False, "blocking_criteria": []}, "verification_reentry": {"status": "NOT_APPLICABLE", "verification_reentry": []}}
    )
    setup_orchestrator = ChatTaskOrchestrator("completion-gap-setup", fixture["mission"]["original_goal"])
    restore_orchestrator_from_runtime_snapshot(
        setup_orchestrator,
        fixture["handoff_packet"],
        session["production_runtime_snapshot"],
    )
    source_task = setup_orchestrator.runtime.tasks["gh-T1"]
    setup_orchestrator.runtime.record_action(
        ActionRecord("A-source", "gh-T1", "tool_call", "run_test_plan", {}, "success", evidence_gain=True)
    )
    setup_orchestrator.runtime.add_evidence(
        EvidenceRecord(
            "E-source",
            "test_safety_run",
            "test://source",
            "source task verified",
            "A-source",
            tool_name="run_test_plan",
            supported_completion_conditions=list(source_task.completion_conditions),
        ),
        ["gh-T1"],
    )
    setup_orchestrator.runtime.support_completion_conditions(
        "gh-T1", "E-source", source_task.completion_conditions
    )
    setup_orchestrator.runtime.evaluate_task_from_evidence("gh-T1")
    session["production_runtime_snapshot"] = setup_orchestrator.snapshot()
    mission_store = SimpleNamespace(
        get_mission=lambda mission_id: fixture["mission"] if mission_id == fixture["mission"]["mission_id"] else None,
        put_mission=lambda _mission: None,
        get_evidence=lambda _evidence_id: None,
        put_evidence=lambda _evidence: None,
    )
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn.MissionMemoryStore.from_default", lambda: mission_store)
    monkeypatch.setattr(
        "ai_tool.chat_interface.agent_turn._record_mission_memory",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr("ai_tool.chat_interface.agent_turn.authorize_tool_execution", lambda *_a, **_k: {"allowed": True})
    monkeypatch.setattr(
        "ai_tool.tool_calling_capability_bridge.apply_tool_calling_hard_capability_bridge",
        lambda *_a, **_k: SimpleNamespace(
            capability_gap=False, routing_performed=False, as_dict=lambda: {}
        ),
    )

    def fake_test_plan(self, _arguments, *, relevant_tools, **_kwargs):
        task_id = self.current_task_id
        task = self.runtime.tasks[task_id]
        action_id = "A-gap"
        evidence_id = "E-gap"
        self.runtime.record_action(ActionRecord(action_id, task_id, "tool_call", "run_test_plan", {}, "success", evidence_gain=True))
        self.runtime.add_evidence(
            EvidenceRecord(
                evidence_id,
                "test_safety_run",
                "test://gap",
                "gap verified",
                action_id,
                tool_name="run_test_plan",
                supported_completion_conditions=list(
                    dict.fromkeys([*task.completion_conditions, TEST_RUN_CLOSED])
                ),
            ),
            [task_id],
        )
        self.runtime.support_completion_conditions(
            task_id, evidence_id, task.completion_conditions
        )
        return {"ok": True, "status": "success", "test_safety": {}}

    monkeypatch.setattr(ChatTaskOrchestrator, "execute_test_plan_action", fake_test_plan)
    chat = lambda **_kwargs: SimpleNamespace(message=SimpleNamespace(
        content="Completion gap verified.",
        tool_calls=[SimpleNamespace(function=SimpleNamespace(name="run_test_plan", arguments={}))],
    ))

    first = run_chat_turn(session, "/run", model="test", chat_fn=chat)
    snapshot = session["production_runtime_snapshot"]
    tasks = {row["task_id"]: row for row in snapshot["tasks"]}
    assert first["runtime_resumed"] is True
    assert tasks["cg-1"]["status"] == "complete"
    assert tasks["cg-1"]["source"] == "completion_gap"
    assert tasks["cg-1"]["source_task_id"] == tasks["gh-T1"]["source_task_id"]
    assert "E-gap" in tasks["cg-1"]["evidence_ids"]
    assert snapshot["completion_gap_acceptance_bindings"] == [{"runtime_task_id": "cg-1", "source_task_id": "T1", "acceptance_id": "A1"}]
    assert session["production_acceptance_evaluation"]["result"]["status"] == "PASS"
    trace = session["production_acceptance_evaluation"]["result"]["criterion_trace"]
    assert trace[0]["evidence_requirement_trace"]["coverage"] == "MATCH"
    assert all(
        row["runtime_task_id"] != "cg-1"
        for row in trace[1]["mapped_runtime_tasks"]
    )
    assert first["goal_acceptance_judgment"]["goal_completed"] is True
    assert first["runtime_goal_closure_report"]["status"] == "CLOSURE_READY"
