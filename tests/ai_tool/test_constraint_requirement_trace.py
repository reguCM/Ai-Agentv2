"""Constraint Requirements reuse the generic identity-only trace contract."""
from __future__ import annotations

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.evidence_requirement_trace import trace_evidence_requirement_identity
from ai_tool.goal_handoff_runtime_bridge import prepare_orchestrator_from_handoff
from tools.ai.task_runtime import EvidenceRecord


def test_constraint_requirement_traces_from_evidence_to_mission_identity() -> None:
    mission = {
        "mission_id": "m-constraint",
        "structured_requirements": [
            {
                "requirement_id": "req-c1",
                "disposition": "CONSTRAINT",
                "constraint_subtype": "prohibition",
                "resolution_status": "resolved",
                "materiality": "blocks_design",
                "normalized_meaning": "Existing files must not be deleted",
            }
        ],
    }
    handoff = {
        "handoff_id": "gh-constraint",
        "source_binding": {"mission_id": "m-constraint", "requirement_ids": ["req-c1"]},
        "implementation_tasks": [
            {"id": "T1", "title": "Preserve existing files", "maps_to_acceptance": ["A1"]}
        ],
        "acceptance_criteria": [
            {"id": "A1", "statement": "Existing files remain", "verification": "inspect workspace"}
        ],
        "requirement_bindings": [
            {"requirement_id": "req-c1", "task_ids": ["T1"], "acceptance_ids": ["A1"]}
        ],
    }
    orchestrator = ChatTaskOrchestrator("constraint-trace", "preserve existing files")
    prepare_orchestrator_from_handoff(orchestrator, handoff)
    orchestrator.runtime.add_evidence(
        EvidenceRecord("E1", "tool", "inspect", "existing files remain", "A1"),
        ["gh-T1"],
    )

    trace = trace_evidence_requirement_identity(
        "E1", runtime=orchestrator.runtime, handoff_packet=handoff, mission=mission
    )

    assert trace["source_task_ids"] == ["T1"]
    assert trace["acceptance_ids"] == ["A1"]
    assert trace["requirement_ids"] == ["req-c1"]
    assert trace["mission_id"] == "m-constraint"
