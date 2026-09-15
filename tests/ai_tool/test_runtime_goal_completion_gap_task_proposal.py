from __future__ import annotations

from copy import deepcopy

from ai_tool.runtime_goal_completion_gap_discovery import (
    discover_runtime_goal_completion_gaps,
)
from ai_tool.runtime_goal_completion_gap_task_proposal import (
    build_runtime_goal_completion_gap_task_proposal,
)
from tests.ai_tool.test_runtime_goal_completion_gap_discovery import _eligible_sources


def _sources() -> tuple[dict, dict, dict]:
    mission, session = _eligible_sources()
    discovery = discover_runtime_goal_completion_gaps(session, mission=mission)
    assert discovery["status"] == "GAP_CANDIDATE"
    return mission, session, deepcopy(discovery["candidates"][0])


def test_proposal_is_identity_grounded_candidate_only() -> None:
    mission, session, candidate = _sources()
    before = deepcopy(session)

    result = build_runtime_goal_completion_gap_task_proposal(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "TASK_PROPOSAL_CANDIDATE"
    proposal = result["proposal"]
    assert proposal == {
        "proposal_type": "COMPLETION_GAP_TASK",
        "proposal_status": "CANDIDATE_ONLY",
        "acceptance_id": "A1",
        "blocker": {
            "acceptance_id": "A1",
            "reason": "acceptance_not_pass",
            "acceptance_judgment": "PASS",
            "meaning_coverage": "MATCH",
        },
        "requirement_ids": ["req-goal"],
        "source_task_ids": ["T1"],
        "runtime_task_ids": ["gh-T1"],
        "evidence_ids": [],
        "proposal_boundary": {
            "creates_runtime_task": False,
            "executes_action": False,
            "adds_evidence": False,
            "registers_acceptance_support": False,
            "persists_to_session": False,
        },
    }
    assert session == before


def test_stale_candidate_does_not_generate_proposal() -> None:
    mission, session, candidate = _sources()
    candidate["runtime_task_ids"] = ["gh-other"]

    result = build_runtime_goal_completion_gap_task_proposal(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "STALE_CANDIDATE"
    assert result["proposal"] is None


def test_existing_work_prevents_proposal() -> None:
    mission, session, candidate = _sources()
    session["production_acceptance_readiness"] = {
        "acceptance_ready": False,
        "incomplete_task_ids": ["gh-T1"],
        "unresolved_failure_ids": [],
        "missing_evidence": [],
    }

    result = build_runtime_goal_completion_gap_task_proposal(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "RETURN_TO_EXISTING_WORK"
    assert result["proposal"] is None
