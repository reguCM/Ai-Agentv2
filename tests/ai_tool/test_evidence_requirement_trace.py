from __future__ import annotations

import pytest

from ai_tool.evidence_requirement_trace import (
    EvidenceRequirementTraceError,
    trace_evidence_requirement_identity,
)
from ai_tool.goal_handoff_runtime_bridge import prepare_orchestrator_from_handoff
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.task_runtime import EvidenceRecord


def _mission(*, requirements: list[dict] | None = None) -> dict:
    return {
        "mission_id": "m-tetris",
        "structured_requirements": requirements
        or [
            {"requirement_id": "req-r3", "normalized_meaning": "操作応答"},
            {"requirement_id": "req-r5", "normalized_meaning": "ゲームオーバーまで遊べる"},
        ],
    }


def _packet(*, task_acceptance: list[str] | None = None, bindings: list[dict] | None = None) -> dict:
    return {
        "handoff_id": "gh-tetris",
        "source_binding": {"mission_id": "m-tetris", "requirement_ids": ["req-r3", "req-r5"]},
        "implementation_tasks": [
            {"id": "T2", "title": "Implement controls", "maps_to_acceptance": task_acceptance or ["A2"]}
        ],
        "acceptance_criteria": [
            {"id": "A2", "statement": "操作入力に反応する", "verification": "manual"},
            {"id": "A3", "statement": "ゲームオーバーまで遊べる", "verification": "manual"},
        ],
        "requirement_bindings": bindings
        if bindings is not None
        else [
            {"requirement_id": "req-r3", "task_ids": ["T2"], "acceptance_ids": ["A2"]},
            {"requirement_id": "req-r5", "task_ids": ["T2"], "acceptance_ids": ["A3"]},
        ],
    }


def _runtime(packet: dict) -> ChatTaskOrchestrator:
    orchestrator = ChatTaskOrchestrator("trace", "高品質なテトリスを作って")
    prepare_orchestrator_from_handoff(orchestrator, packet)
    orchestrator.runtime.add_evidence(
        EvidenceRecord(
            evidence_id="E1", source_type="tool", source="run_test", summary="controls pass", created_by_action="A1"
        ),
        ["gh-T2"],
    )
    return orchestrator


def _trace(packet: dict | None = None, mission: dict | None = None) -> dict:
    packet = packet or _packet()
    orchestrator = _runtime(packet)
    return trace_evidence_requirement_identity("E1", runtime=orchestrator.runtime, handoff_packet=packet, mission=mission or _mission())


def test_tetris_evidence_trace_composes_forward_and_reverse_identity() -> None:
    assert _trace() == {
        "evidence_id": "E1", "runtime_task_ids": ["gh-T2"], "source_task_ids": ["T2"],
        "acceptance_ids": ["A2"], "requirement_ids": ["req-r3"], "mission_id": "m-tetris",
        "task_traces": [{"runtime_task_id": "gh-T2", "source_task_id": "T2", "acceptance_ids": ["A2"], "requirement_ids": ["req-r3"]}],
    }


def test_one_task_maps_to_multiple_acceptances() -> None:
    trace = _trace(_packet(task_acceptance=["A2", "A3"]))
    assert trace["acceptance_ids"] == ["A2", "A3"]
    assert trace["requirement_ids"] == ["req-r3", "req-r5"]


def test_one_acceptance_maps_to_multiple_requirements() -> None:
    packet = _packet(bindings=[
        {"requirement_id": "req-r3", "task_ids": ["T2"], "acceptance_ids": ["A2"]},
        {"requirement_id": "req-r5", "task_ids": [], "acceptance_ids": ["A2"]},
    ])
    assert _trace(packet)["requirement_ids"] == ["req-r3", "req-r5"]


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda packet, runtime, mission: runtime.runtime.evidence["E1"].task_ids.__setitem__(0, "gh-T99"), "runtime_task_not_found:gh-T99"),
        (lambda packet, runtime, mission: setattr(runtime.runtime.tasks["gh-T2"], "source_task_id", None), "missing_source_task_id:gh-T2"),
        (lambda packet, runtime, mission: setattr(runtime.runtime.tasks["gh-T2"], "source_task_id", "T99"), "handoff_task_not_found:T99"),
        (lambda packet, runtime, mission: packet["implementation_tasks"][0].update({"maps_to_acceptance": ["A99"]}), "unknown_task_acceptance:T2:A99"),
        (lambda packet, runtime, mission: packet.update({"requirement_bindings": []}), "acceptance_has_no_requirement_binding:A2"),
        (lambda packet, runtime, mission: mission["structured_requirements"].pop(0), "source_binding_mismatch:source_requirement_mismatch"),
        (lambda packet, runtime, mission: packet["source_binding"].update({"mission_id": "m-other"}), "source_binding_mismatch:source_mission_mismatch"),
    ],
)
def test_trace_fails_closed_for_missing_or_mismatched_identities(mutate, error: str) -> None:
    packet = _packet()
    mission = _mission()
    runtime = _runtime(packet)
    mutate(packet, runtime, mission)
    with pytest.raises(EvidenceRequirementTraceError, match=error):
        trace_evidence_requirement_identity("E1", runtime=runtime.runtime, handoff_packet=packet, mission=mission)


def test_trace_survives_runtime_snapshot_reload() -> None:
    packet = _packet()
    first = _runtime(packet)
    snapshot = first.snapshot()
    restored = ChatTaskOrchestrator("trace-resume", "高品質なテトリスを作って")
    # The trace needs neither sandbox state nor an executing Runtime to prove identity restoration.
    restored.apply_completion_runtime(snapshot, replace_graph=True)
    assert trace_evidence_requirement_identity("E1", runtime=restored.runtime, handoff_packet=packet, mission=_mission())["task_traces"] == [
        {"runtime_task_id": "gh-T2", "source_task_id": "T2", "acceptance_ids": ["A2"], "requirement_ids": ["req-r3"]}
    ]
