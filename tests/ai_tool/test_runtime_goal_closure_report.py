from __future__ import annotations

from copy import deepcopy

from ai_tool.dev_skill_pipeline import build_handoff_packet
from ai_tool.goal_handoff_source_binding import build_handoff_source_binding
from ai_tool.production_meaning_context import build_meaning_context_v0
from ai_tool.production_run_contract import build_production_run_contract
from ai_tool.runtime_goal_closure_report import (
    build_runtime_goal_closure_report,
    canonical_handoff_hash,
)


def _sources():
    mission = {
        "schema_version": "1",
        "mission_id": "m-closure",
        "original_goal": "build calculator",
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        "structured_requirements": [
            {
                "requirement_id": "req-goal",
                "source_text": "build calculator",
                "source_span": [0, 16],
                "disposition": "GOAL",
                "resolution_status": "resolved",
                "provenance": "user_explicit",
                "materiality": "blocks_design",
                "normalized_meaning": "build calculator",
            }
        ],
        "confirmed_clarifications": [],
    }
    handoff = build_handoff_packet(
        initial_request="build calculator",
        aligned_spec={
            "summary": "build calculator",
            "numbered_conditions": ["four operations work"],
            "non_goals": [],
            "acceptance_criteria": ["four operations work"],
        },
        prd_rel="design/prd.md",
        tech_spec_rel="design/tech.md",
        plan_rel="design/plan.md",
        todo_rel="design/todo.md",
        tech_spec={"summary": "calculator", "modules": [{"path": "calculator.py"}]},
        plan={
            "tasks": [
                {
                    "id": "T1",
                    "title": "implement calculator",
                    "acceptance": ["four operations work"],
                    "verification": ["run focused test"],
                    "size": "S",
                    "dependencies": [],
                }
            ],
            "requirement_bindings": [
                {
                    "requirement_id": "req-goal",
                    "task_ids": ["T1"],
                    "acceptance_ids": ["A1"],
                }
            ],
        },
        skill_steps=["production-handoff"],
        handoff_slug="closure",
        source_binding=build_handoff_source_binding(mission),
        structured_requirements=mission["structured_requirements"],
    )
    # The generic builder's placeholder E2E list is empty; this fixture must
    # represent a schema-valid saved Handoff before it can be read-only checked.
    handoff["test_plan"]["e2e"] = ["run calculator end-to-end verification"]
    meaning = build_meaning_context_v0(mission, handoff)
    handoff_hash = canonical_handoff_hash(handoff)
    runtime = {
        "goals": [{"goal_id": "G1", "status": "complete"}],
        "tasks": [{"task_id": "gh-T1", "status": "complete"}],
    }
    contract = build_production_run_contract(
        started_execution_id="exec-closure",
        mission=mission,
        handoff=handoff,
        meaning_context=meaning,
        starting_task_id="gh-T1",
        handoff_canonical_hash=handoff_hash,
    )
    acceptance = {
        "status": "PASS",
        "criterion_trace": [
            {"acceptance_id": "A1", "evidence_requirement_trace": {"coverage": "MATCH"}}
        ],
        "meaning_trace_audit": {
            "criteria_count": 1,
            "criteria": [
                {
                    "acceptance_id": "A1",
                    "acceptance_judgment": "PASS",
                    "meaning_coverage": "MATCH",
                }
            ],
        },
    }
    session = {
        "production_handoff_packet": handoff,
        "production_meaning_context": meaning,
        "production_run_contract": contract,
        "production_runtime_snapshot": runtime,
        "production_runtime_handoff_integrity": {
            "handoff_id": handoff["handoff_id"],
            "canonical_hash": handoff_hash,
        },
        "production_acceptance_readiness": {
            "acceptance_ready": True,
            "incomplete_task_ids": [],
            "unresolved_failure_ids": [],
            "missing_evidence": [],
        },
        "production_acceptance_evaluation": {
            "handoff_id": handoff["handoff_id"],
            "canonical_hash": handoff_hash,
            "result": acceptance,
        },
        "production_goal_acceptance_judgment": {
            "handoff_id": handoff["handoff_id"],
            "canonical_hash": handoff_hash,
            "goal_completed": True,
            "completion_eligibility": {"completion_eligible": True, "blocking_criteria": []},
        },
    }
    return mission, session


def test_report_is_closure_ready_only_for_consistent_existing_facts():
    mission, session = _sources()
    before = deepcopy(session)
    report = build_runtime_goal_closure_report(session, mission=mission)
    assert report["status"] == "CLOSURE_READY"
    assert not report["blockers"]
    assert session == before
    assert {row["name"] for row in report["checks"]} >= {
        "handoff",
        "run_contract",
        "acceptance",
        "meaning_completion_eligibility",
        "goal_judgment",
        "runtime_goal",
    }


def test_report_is_not_ready_when_existing_meaning_eligibility_blocks_completion():
    mission, session = _sources()
    acceptance = session["production_acceptance_evaluation"]["result"]
    acceptance["criterion_trace"][0]["evidence_requirement_trace"]["coverage"] = "MISMATCH"
    acceptance["meaning_trace_audit"]["criteria"][0]["meaning_coverage"] = "MISMATCH"
    session["production_goal_acceptance_judgment"]["goal_completed"] = False
    session["production_goal_acceptance_judgment"]["completion_eligibility"] = {
        "completion_eligible": False,
        "blocking_criteria": [
            {
                "acceptance_id": "A1",
                "acceptance_judgment": "PASS",
                "meaning_coverage": "MISMATCH",
                "reason": "meaning_not_completion_eligible",
            }
        ],
    }
    report = build_runtime_goal_closure_report(session, mission=mission)
    assert report["status"] == "NOT_READY"
    assert {row["code"] for row in report["blockers"]} >= {
        "meaning_not_completion_eligible",
        "goal_not_completed",
    }


def test_report_is_inconclusive_for_mismatched_saved_identity():
    mission, session = _sources()
    session["production_runtime_handoff_integrity"]["handoff_id"] = "gh-other"
    report = build_runtime_goal_closure_report(session, mission=mission)
    assert report["status"] == "INCONCLUSIVE"
    assert "runtime_handoff_identity_mismatch" in {row["code"] for row in report["blockers"]}
