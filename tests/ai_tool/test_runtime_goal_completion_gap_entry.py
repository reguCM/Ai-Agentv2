from __future__ import annotations

from copy import deepcopy

from ai_tool.runtime_goal_completion_gap_entry import (
    assess_runtime_goal_completion_gap_entry,
)
from tests.ai_tool.test_runtime_goal_closure_report import _sources


def _assessment(session: dict, mission: dict) -> dict:
    before = deepcopy(session)
    result = assess_runtime_goal_completion_gap_entry(session, mission=mission)
    assert session == before
    return result


def test_completed_goal_is_not_a_level4_candidate() -> None:
    mission, session = _sources()
    assert _assessment(session, mission)["status"] == "NOT_APPLICABLE_COMPLETED"


def test_invalid_identity_fails_closed_before_level4() -> None:
    mission, session = _sources()
    session["production_runtime_handoff_integrity"]["handoff_id"] = "other"
    assert _assessment(session, mission)["status"] == "FAIL_CLOSED_IDENTITY"


def test_incomplete_existing_work_returns_to_level1_or_level2() -> None:
    mission, session = _sources()
    session["production_acceptance_readiness"] = {
        "acceptance_ready": False,
        "incomplete_task_ids": ["gh-T1"],
        "unresolved_failure_ids": [],
        "missing_evidence": [{"task_id": "gh-T1", "condition": "four operations work"}],
    }
    result = _assessment(session, mission)
    assert result["status"] == "RETURN_TO_EXISTING_WORK"
    assert result["readiness"]["incomplete_task_ids"] == ["gh-T1"]


def test_meaning_mismatch_uses_existing_verification_reentry() -> None:
    mission, session = _sources()
    acceptance = session["production_acceptance_evaluation"]["result"]
    acceptance["criterion_trace"][0]["evidence_requirement_trace"] = {
        "coverage": "MISMATCH",
        "expected_requirement_ids": ["req-goal"],
    }
    acceptance["meaning_trace_audit"]["criteria"][0]["meaning_coverage"] = "MISMATCH"
    session["production_goal_acceptance_judgment"]["goal_completed"] = False
    session["production_goal_acceptance_judgment"]["completion_eligibility"] = {
        "completion_eligible": False,
        "blocking_criteria": [],
    }
    result = _assessment(session, mission)
    assert result["status"] == "RETURN_TO_VERIFICATION_REENTRY"


def test_acceptance_failure_after_existing_work_is_level4_candidate_only() -> None:
    mission, session = _sources()
    acceptance = session["production_acceptance_evaluation"]["result"]
    acceptance["status"] = "FAIL"
    session["production_goal_acceptance_judgment"]["goal_completed"] = False
    session["production_goal_acceptance_judgment"]["completion_eligibility"] = {
        "completion_eligible": False,
        "blocking_criteria": [],
    }
    session["production_runtime_snapshot"]["goals"][0]["status"] = "in_progress"
    result = _assessment(session, mission)
    assert result["status"] == "ELIGIBLE_FOR_COMPLETION_GAP_DISCOVERY"
    assert result["blocking_criteria"] == [
        {
            "acceptance_id": "A1",
            "acceptance_judgment": "PASS",
            "meaning_coverage": "MATCH",
            "reason": "acceptance_not_pass",
        }
    ]
