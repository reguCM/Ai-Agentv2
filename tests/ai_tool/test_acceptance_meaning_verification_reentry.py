from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from ai_tool.acceptance_meaning_verification_reentry import (
    build_acceptance_meaning_verification_reentry,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.verification_only_execution import execute_verification_only_reentry
from tools.ai.task_runtime import ActionRecord, EvidenceRecord, TaskStatus


def _mission() -> dict:
    return {
        "mission_id": "m-tetris",
        "structured_requirements": [
            {"requirement_id": "R2", "normalized_meaning": "board"},
            {"requirement_id": "R3", "normalized_meaning": "controls"},
            {"requirement_id": "R8", "normalized_meaning": "other"},
        ],
    }


def _packet() -> dict:
    return {
        "handoff_id": "gh-tetris",
        "source_binding": {"mission_id": "m-tetris", "requirement_ids": ["R2", "R3", "R8"]},
        "acceptance_criteria": [{"id": "A2", "statement": "controls"}, {"id": "A8", "statement": "other"}],
        "implementation_tasks": [
            {"id": "T2", "maps_to_acceptance": ["A2"]},
            {"id": "T3", "maps_to_acceptance": ["A2"]},
            {"id": "T8", "maps_to_acceptance": ["A8"]},
        ],
        "requirement_bindings": [
            {"requirement_id": "R2", "task_ids": ["T2"], "acceptance_ids": ["A2"]},
            {"requirement_id": "R3", "task_ids": ["T3"], "acceptance_ids": ["A2"]},
            {"requirement_id": "R8", "task_ids": ["T8"], "acceptance_ids": ["A8"]},
        ],
    }


def _runtime(packet: dict) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("reentry", "tetris")
    seed_orchestrator_from_handoff(orchestrator, packet)
    return orchestrator


def _result(*, coverage: str, expected: list[str], observed: list[str], evidence: list[str], status: str = "PASS") -> dict:
    return {
        "status": status,
        "criterion_trace": [{"acceptance_id": "A2", "evidence_requirement_trace": {"coverage": coverage, "expected_requirement_ids": expected}}],
        "meaning_trace_audit": {
            "criteria_count": 1,
            "criteria": [{"acceptance_id": "A2", "acceptance_judgment": status, "meaning_coverage": coverage, "observed_requirement_ids": observed, "evidence_ids": evidence}],
        },
    }


def _reentry(result: dict, packet: dict | None = None, runtime=None) -> dict:
    packet = packet or _packet()
    return build_acceptance_meaning_verification_reentry(
        result, handoff_packet=packet, mission=_mission(), runtime=runtime or _runtime(packet).runtime
    )


def test_partial_targets_only_the_missing_requirement_task() -> None:
    context = _reentry(_result(coverage="PARTIAL", expected=["R2", "R3"], observed=["R2"], evidence=["E2"]))
    assert context["status"] == "VERIFICATION_REENTRY_CONTEXT_READY"
    assert context["verification_reentry"] == [{
        "acceptance_id": "A2", "meaning_coverage": "PARTIAL", "expected_requirement_ids": ["R2", "R3"],
        "observed_requirement_ids": ["R2"], "evidence_ids": ["E2"], "requirement_ids": ["R3"],
        "source_task_ids": ["T3"], "runtime_task_ids": ["gh-T3"],
        "reason": "meaning_partial_requires_verification",
    }]


def test_mismatch_targets_expected_requirement_and_never_reuses_wrong_evidence() -> None:
    context = _reentry(_result(coverage="MISMATCH", expected=["R3"], observed=["R8"], evidence=["E5"]))
    entry = context["verification_reentry"][0]
    assert entry["requirement_ids"] == ["R3"]
    assert entry["source_task_ids"] == ["T3"]
    assert entry["runtime_task_ids"] == ["gh-T3"]
    assert entry["evidence_ids"] == ["E5"]  # audit-only: no reuse field exists


def test_untraceable_uses_acceptance_requirement_task_identity_path() -> None:
    context = _reentry(_result(coverage="UNTRACEABLE", expected=["R3"], observed=[], evidence=[]))
    assert context["status"] == "VERIFICATION_REENTRY_CONTEXT_READY"
    assert context["verification_reentry"][0]["runtime_task_ids"] == ["gh-T3"]


def test_untraceable_with_missing_task_identity_fails_closed() -> None:
    packet = _packet()
    packet["requirement_bindings"][1]["task_ids"] = ["T404"]
    context = _reentry(_result(coverage="UNTRACEABLE", expected=["R3"], observed=[], evidence=[]), packet)
    assert context["status"] == "VERIFICATION_REENTRY_UNRESOLVED"
    assert context["verification_reentry"] == []
    assert context["errors"] == ["requirement_task_identity_missing:A2:R3"]


def test_match_and_acceptance_fail_do_not_request_reentry() -> None:
    assert _reentry(_result(coverage="MATCH", expected=["R3"], observed=["R3"], evidence=["E1"])) == {
        "status": "NOT_APPLICABLE", "verification_reentry": []
    }
    assert _reentry(_result(coverage="MISMATCH", expected=["R3"], observed=["R8"], evidence=["E5"], status="FAIL")) == {
        "status": "NOT_APPLICABLE", "verification_reentry": []
    }


def test_runtime_snapshot_reload_derives_the_same_context() -> None:
    packet = _packet()
    original = _runtime(packet)
    result = _result(coverage="MISMATCH", expected=["R3"], observed=["R8"], evidence=["E5"])
    before = _reentry(result, packet, original.runtime)
    restored = ChatTaskOrchestrator("reentry-restored", "tetris")
    restored.apply_completion_runtime(deepcopy(original.snapshot()), replace_graph=True)
    after = _reentry(result, packet, restored.runtime)
    assert after == before


def test_session_reload_keeps_the_same_derived_reentry_context(monkeypatch, tmp_path) -> None:
    import ai_tool.chat_interface.chat_session as sessions
    from ai_tool.chat_interface.chat_session import load_session, save_session

    monkeypatch.setattr(sessions, "SESSIONS_DIR", tmp_path / "sessions")
    context = _reentry(_result(coverage="UNTRACEABLE", expected=["R3"], observed=[], evidence=[]))
    save_session({
        "session_id": "verification-reentry",
        "production_goal_acceptance_judgment": {"verification_reentry": context},
    })
    assert load_session("verification-reentry")["production_goal_acceptance_judgment"]["verification_reentry"] == context


def test_verification_only_execution_appends_action_and_evidence_without_reopening_task() -> None:
    packet = _packet()
    packet["test_plan"] = {"plan_id": "p1", "pytest": ["tests/test_tetris.py"]}
    packet["implementation_tasks"][1]["verification"] = ["pytest tests/test_tetris.py"]
    orchestrator = _runtime(packet)
    runtime = orchestrator.runtime
    runtime.sandbox_session = SimpleNamespace(status="ACTIVE")
    target = runtime.tasks["gh-T3"]
    target.status = TaskStatus.COMPLETE.value
    reentry = _reentry(_result(coverage="MISMATCH", expected=["R3"], observed=["R8"], evidence=["E5"]), packet, runtime)
    old_actions, old_evidence = list(runtime.actions), dict(runtime.evidence)

    def execute(_orch, task_id, _args):
        runtime.record_verification_action(ActionRecord("A-v", task_id, "verification_only", "run_test_plan", {}, "success"))
        runtime.add_evidence(EvidenceRecord("E-v", "test", "test://v", "verified", "A-v", tool_name="run_test_plan"), [task_id])
        return {"status": "success"}

    result = execute_verification_only_reentry(orchestrator, reentry, execute_action=execute)
    assert result["status"] == "VERIFICATION_EXECUTED"
    assert target.status == TaskStatus.COMPLETE.value
    assert runtime.actions[: len(old_actions)] == old_actions
    assert all(runtime.evidence[key] is value for key, value in old_evidence.items())
    assert result["new_action_ids"] == ["A-v"]
    assert result["new_evidence_ids"] == ["E-v"]


def test_verification_only_rejects_missing_sandbox_or_untraceable_context() -> None:
    packet = _packet()
    packet["test_plan"] = {"pytest": ["tests/test_tetris.py"]}
    packet["implementation_tasks"][1]["verification"] = ["pytest"]
    orchestrator = _runtime(packet)
    orchestrator.runtime.tasks["gh-T3"].status = TaskStatus.COMPLETE.value
    reentry = _reentry(_result(coverage="UNTRACEABLE", expected=["R3"], observed=[], evidence=[]), packet, orchestrator.runtime)
    assert execute_verification_only_reentry(orchestrator, reentry)["reason"] == "active_sandbox_required"
