from __future__ import annotations

from copy import deepcopy

from ai_tool.runtime_goal_completion_gap_discovery import (
    discover_runtime_goal_completion_gaps,
)
from tests.ai_tool.test_runtime_goal_closure_report import _sources


def _eligible_sources() -> tuple[dict, dict]:
    mission, session = _sources()
    acceptance = session["production_acceptance_evaluation"]["result"]
    acceptance["status"] = "FAIL"
    session["production_goal_acceptance_judgment"]["goal_completed"] = False
    session["production_goal_acceptance_judgment"]["completion_eligibility"] = {
        "completion_eligible": False,
        "blocking_criteria": [],
    }
    session["production_runtime_snapshot"]["goals"][0]["status"] = "in_progress"
    return mission, session


def test_eligible_entry_derives_identity_only_gap_candidate() -> None:
    mission, session = _eligible_sources()
    before = deepcopy(session)

    result = discover_runtime_goal_completion_gaps(session, mission=mission)

    assert result["status"] == "GAP_CANDIDATE"
    assert result["handoff_id"] == session["production_handoff_packet"]["handoff_id"]
    assert result["run_execution_id"] == "exec-closure"
    assert result["candidates"] == [
        {
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
        }
    ]
    assert session == before


def test_completed_goal_has_no_discoverable_gap() -> None:
    mission, session = _sources()
    assert discover_runtime_goal_completion_gaps(session, mission=mission)["status"] == "NO_DISCOVERABLE_GAP"


def test_human_meaning_entry_returns_human_required(monkeypatch) -> None:
    mission, session = _sources()
    monkeypatch.setattr(
        "ai_tool.runtime_goal_completion_gap_discovery.assess_runtime_goal_completion_gap_entry",
        lambda *_args, **_kwargs: {
            "status": "RETURN_TO_HUMAN_MEANING",
            "handoff_id": "gh-closure",
            "run_execution_id": "exec-closure",
        },
    )

    assert discover_runtime_goal_completion_gaps(session, mission=mission)["status"] == "HUMAN_REQUIRED"


def test_missing_runtime_mapping_fails_closed(monkeypatch) -> None:
    mission, session = _eligible_sources()
    session["production_runtime_snapshot"]["tasks"] = []
    monkeypatch.setattr(
        "ai_tool.runtime_goal_completion_gap_discovery.assess_runtime_goal_completion_gap_entry",
        lambda *_args, **_kwargs: {
            "status": "ELIGIBLE_FOR_COMPLETION_GAP_DISCOVERY",
            "handoff_id": session["production_handoff_packet"]["handoff_id"],
            "run_execution_id": "exec-closure",
            "blocking_criteria": [
                {
                    "acceptance_id": "A1",
                    "reason": "acceptance_not_pass",
                    "acceptance_judgment": "PASS",
                    "meaning_coverage": "MATCH",
                }
            ],
        },
    )

    result = discover_runtime_goal_completion_gaps(session, mission=mission)

    assert result["status"] == "FAIL_CLOSED"
    assert result["errors"] == ["runtime_task_mapping_not_found:A1"]
