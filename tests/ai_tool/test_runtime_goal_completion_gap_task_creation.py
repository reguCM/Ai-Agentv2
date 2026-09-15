from __future__ import annotations

from copy import deepcopy

from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
from ai_tool.runtime_goal_completion_gap_discovery import (
    discover_runtime_goal_completion_gaps,
)
from ai_tool.runtime_goal_completion_gap_task_creation import (
    create_runtime_goal_completion_gap_task,
)
from tests.ai_tool.test_runtime_goal_completion_gap_discovery import _eligible_sources


def _sources() -> tuple[dict, dict, dict, ChatTaskOrchestrator]:
    mission, session = _eligible_sources()
    discovery = discover_runtime_goal_completion_gaps(session, mission=mission)
    candidate = deepcopy(discovery["candidates"][0])
    orchestrator = ChatTaskOrchestrator("completion-gap-creation", "goal")
    seed_orchestrator_from_handoff(orchestrator, session["production_handoff_packet"])
    source = orchestrator.runtime.tasks["gh-T1"]
    source.status = "complete"
    return mission, session, candidate, orchestrator


def test_creates_pending_runtime_task_and_acceptance_support_relation() -> None:
    mission, session, candidate, orchestrator = _sources()
    session_before = deepcopy(session)

    result = create_runtime_goal_completion_gap_task(
        orchestrator, session, mission=mission, candidate=candidate
    )

    assert result["status"] == "TASK_CREATED"
    assert result["task"] == {
        "task_id": "cg-1",
        "goal_id": "G1",
        "status": "pending",
        "source": "completion_gap",
        "source_task_id": "T1",
        "depends_on": ["gh-T1"],
    }
    assert result["acceptance_support_relation"] == {
        "runtime_task_id": "cg-1",
        "source_task_id": "T1",
        "acceptance_id": "A1",
    }
    assert orchestrator.runtime.tasks["cg-1"].status == "pending"
    assert len(orchestrator.runtime.actions) == 0
    assert len(orchestrator.runtime.evidence) == 0
    assert session == session_before


def test_stale_candidate_creates_no_task() -> None:
    mission, session, candidate, orchestrator = _sources()
    candidate["run_execution_id"] = "stale"

    result = create_runtime_goal_completion_gap_task(
        orchestrator, session, mission=mission, candidate=candidate
    )

    assert result["status"] == "STALE_CANDIDATE"
    assert "cg-1" not in orchestrator.runtime.tasks


def test_existing_gap_task_is_not_duplicated() -> None:
    mission, session, candidate, orchestrator = _sources()
    first = create_runtime_goal_completion_gap_task(
        orchestrator, session, mission=mission, candidate=candidate
    )
    second = create_runtime_goal_completion_gap_task(
        orchestrator, session, mission=mission, candidate=candidate
    )

    assert first["status"] == "TASK_CREATED"
    assert second == {
        "status": "ALREADY_CREATED",
        "handoff_id": first["handoff_id"],
        "run_execution_id": first["run_execution_id"],
        "proposal": first["proposal"],
        "runtime_task_id": "cg-1",
    }
    assert list(orchestrator.runtime.tasks) == ["gh-T1", "cg-1"]
