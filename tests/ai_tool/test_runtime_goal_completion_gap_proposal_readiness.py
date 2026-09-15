from __future__ import annotations

from copy import deepcopy

from ai_tool.runtime_goal_completion_gap_discovery import (
    discover_runtime_goal_completion_gaps,
)
from ai_tool.runtime_goal_completion_gap_proposal_readiness import (
    assess_runtime_goal_completion_gap_proposal_readiness,
)
from tests.ai_tool.test_runtime_goal_completion_gap_discovery import _eligible_sources
from tests.ai_tool.test_runtime_goal_closure_report import _sources


def _candidate() -> tuple[dict, dict, dict]:
    mission, session = _eligible_sources()
    discovery = discover_runtime_goal_completion_gaps(session, mission=mission)
    assert discovery["status"] == "GAP_CANDIDATE"
    return mission, session, deepcopy(discovery["candidates"][0])


def test_current_candidate_is_ready_without_mutating_session() -> None:
    mission, session, candidate = _candidate()
    before = deepcopy(session)

    result = assess_runtime_goal_completion_gap_proposal_readiness(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "PROPOSAL_READY"
    assert result["candidate"] == candidate
    assert session == before


def test_prior_candidate_with_other_run_is_stale() -> None:
    mission, session, candidate = _candidate()
    candidate["run_execution_id"] = "older-run"

    result = assess_runtime_goal_completion_gap_proposal_readiness(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "STALE_CANDIDATE"
    assert result["reason"] == "candidate_run_identity_mismatch"


def test_existing_work_now_prevents_proposal() -> None:
    mission, session, candidate = _candidate()
    session["production_acceptance_readiness"] = {
        "acceptance_ready": False,
        "incomplete_task_ids": ["gh-T1"],
        "unresolved_failure_ids": [],
        "missing_evidence": [],
    }

    result = assess_runtime_goal_completion_gap_proposal_readiness(
        session, mission=mission, candidate=candidate
    )

    assert result["status"] == "RETURN_TO_EXISTING_WORK"


def test_missing_candidate_identity_fails_closed() -> None:
    mission, session, _candidate_row = _candidate()

    result = assess_runtime_goal_completion_gap_proposal_readiness(
        session, mission=mission, candidate={"acceptance_id": "A1"}
    )

    assert result["status"] == "FAIL_CLOSED"
    assert result["reason"] == "missing_candidate_identity"


def test_completed_goal_has_no_proposal_candidate() -> None:
    mission, session = _sources()
    result = assess_runtime_goal_completion_gap_proposal_readiness(
        session, mission=mission, candidate=None
    )
    assert result["status"] == "NO_PROPOSAL_CANDIDATE"
