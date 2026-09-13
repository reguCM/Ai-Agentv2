"""CPU-deterministic tests for Human Decision premise tracking."""
from __future__ import annotations

from ai_tool.chat_interface.decision_change_gate import (
    DECISION_STATUS_CONFIRMED,
    DECISION_STATUS_SUPERSEDED,
    supersede_decision,
)
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.human_decision_premise import (
    INITIAL_GRILL_SOURCE,
    build_initial_grill_decision_record,
    tasks_needing_revalidation,
)


DECISION_KEY = "acceptance:output_format"
D1 = "d19-v1"
D2 = "d19-v2"


def _handoff_packet() -> dict:
    return {
        "handoff_id": "gh-decision-premise",
        "goal": {"summary": "Report probe.txt using the confirmed output format"},
        "scope": {
            "in_scope": ["probe.txt reported"],
            "affected_paths": ["probe.txt"],
        },
        "acceptance_criteria": [
            {
                "id": "A1",
                "statement": "probe.txt is reported",
                "verification": "read_file",
            }
        ],
        "implementation_tasks": [
            {
                "id": "T1",
                "title": "Read probe.txt",
                "acceptance": ["probe.txt content observed"],
                "verification": ["read_file succeeds"],
                "dependencies": [],
                "size": "S",
            },
            {
                "id": "T2",
                "title": "Report probe.txt in the confirmed format",
                "acceptance": ["report matches confirmed output format"],
                "verification": ["human-readable answer produced"],
                "dependencies": ["T1"],
                "size": "S",
                "decision_premises": [
                    {
                        "decision_key": DECISION_KEY,
                        "derived_from_decision_id": D1,
                    }
                ],
            },
        ],
    }


def _orchestrator_with_decision_a() -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("premise-track", "report probe.txt")
    orchestrator.mission_id = "m-premise"
    orchestrator.execution_id = "exec-1"
    orchestrator.confirmed_clarifications = [
        {
            "decision_id": D1,
            "decision_key": DECISION_KEY,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "A: quote first lines",
            "dimension": "acceptance",
        }
    ]
    seed_orchestrator_from_handoff(orchestrator, _handoff_packet())
    return orchestrator


def test_initial_grill_decision_record_has_required_fields():
    record = build_initial_grill_decision_record(
        "docs/PROJECT_SPEC.md",
        decision_key="target:identity:multiple-confirmed-paths-in-candidates:q-project-spec:p-dot",
        extracted_path_grounds=["docs/PROJECT_SPEC.md"],
    )
    assert record["decision_id"]
    assert record["decision_key"].startswith("target:identity:")
    assert record["status"] == DECISION_STATUS_CONFIRMED
    assert record["source"] == INITIAL_GRILL_SOURCE


def test_handoff_seed_preserves_decision_premises_on_runtime_task():
    orchestrator = _orchestrator_with_decision_a()
    t1 = orchestrator.runtime.tasks["gh-T1"]
    t2 = orchestrator.runtime.tasks["gh-T2"]
    assert t1.decision_premises == []
    assert t2.decision_premises == [
        {
            "decision_key": DECISION_KEY,
            "derived_from_decision_id": D1,
            "validated_against_decision_id": D1,
        }
    ]
    assert t2.revalidation == {
        "needs_revalidation": False,
        "affected": False,
        "decision_premises": t2.decision_premises,
        "active_decision_ids": {DECISION_KEY: D1},
        "validated_decision_ids": {DECISION_KEY: D1},
        "derived_decision_ids": {DECISION_KEY: D1},
    }
    assert t2.decision_premises[0]["validated_against_decision_id"] == D1


def test_completion_runtime_restore_preserves_decision_premises():
    orchestrator = _orchestrator_with_decision_a()
    snapshot = orchestrator.completion_runtime_slice()
    resumed = ChatTaskOrchestrator("premise-resume", orchestrator.request)
    resumed.confirmed_clarifications = list(orchestrator.confirmed_clarifications)
    resumed.apply_completion_runtime(snapshot, replace_graph=True)
    t2 = resumed.runtime.tasks["gh-T2"]
    assert t2.decision_premises == [
        {
            "decision_key": DECISION_KEY,
            "derived_from_decision_id": D1,
            "validated_against_decision_id": D1,
        }
    ]
    assert t2.revalidation["needs_revalidation"] is False


def test_supersede_marks_only_dependent_handoff_task_for_revalidation():
    orchestrator = _orchestrator_with_decision_a()
    resumed = ChatTaskOrchestrator("premise-supersede", orchestrator.request)
    resumed.confirmed_clarifications = list(orchestrator.confirmed_clarifications)
    resumed.apply_completion_runtime(
        orchestrator.completion_runtime_slice(),
        replace_graph=True,
    )
    resumed.mission_id = orchestrator.mission_id
    resumed.execution_id = "exec-2"

    supersede_decision(
        resumed,
        D1,
        {
            "source": "boundary_grill",
            "decision_key": DECISION_KEY,
            "text": "B: one-paragraph summary",
            "decision_id": D2,
            "status": DECISION_STATUS_CONFIRMED,
            "dimension": "acceptance",
        },
        execution_id="exec-2",
    )

    active = [
        row
        for row in resumed.confirmed_clarifications
        if row.get("status") != DECISION_STATUS_SUPERSEDED
        and row.get("decision_key") == DECISION_KEY
    ]
    assert len(active) == 1
    assert active[0]["decision_id"] == D2
    assert active[0]["text"].startswith("B:")

    t1 = resumed.runtime.tasks["gh-T1"]
    t2 = resumed.runtime.tasks["gh-T2"]
    assert t1.revalidation is None
    assert t2.revalidation["needs_revalidation"] is True
    assert t2.revalidation["affected"] is True
    assert t2.revalidation["stale_decision_ids"] == [D1]
    assert t2.revalidation["active_decision_ids"] == {DECISION_KEY: D2}
    assert t2.decision_premises[0]["derived_from_decision_id"] == D1
    assert t2.decision_premises[0]["validated_against_decision_id"] == D1

    affected = tasks_needing_revalidation(resumed)
    assert [row["task_id"] for row in affected] == ["gh-T2"]
