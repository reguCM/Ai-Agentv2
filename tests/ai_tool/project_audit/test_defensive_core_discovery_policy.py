"""Tests for Defensive Core Discovery Policy integration."""
from __future__ import annotations

from ai_tool.defensive_core_discovery_policy import (
    anti_overengineering_rules,
    build_mandatory_phase_report,
    classification_rules,
    discovery_questions,
    existing_core_registry,
    phase_core_candidates,
    policy_summary_for_harnesses,
    policy_tracks,
    run_defensive_core_discovery_policy_integration,
)


def test_two_track_policy_defined():
    tracks = policy_tracks()
    assert "track_a_current_problem" in tracks
    assert "track_b_future_core" in tracks


def test_discovery_questions_eight():
    qs = discovery_questions()
    assert len(qs) == 8
    assert any(q["id"] == "Q8" for q in qs)


def test_llm_capability_role_criteria():
    from ai_tool.defensive_core_discovery_policy import (
        evaluate_llm_capability_role,
        llm_capability_role_criteria,
    )

    crit = llm_capability_role_criteria()
    assert crit["mechanical_verification_not_mechanical_answer"] is True
    assert evaluate_llm_capability_role(extends_llm=True, replaces_llm=False) == "FAVOR_RECORD_OR_EXPERIMENTAL"
    assert "DEFER" in evaluate_llm_capability_role(extends_llm=False, replaces_llm=True)


def test_classification_c0_through_c4():
    rules = classification_rules()
    for c in ("C0", "C1", "C2", "C3", "C4"):
        assert c in rules


def test_existing_core_registry_has_cc01_and_mechanical():
    reg = existing_core_registry()
    ids = {r.id for r in reg}
    assert "CC-01" in ids
    assert "CC-02" in ids
    cc01 = next(r for r in reg if r.id == "CC-01")
    assert cc01.reuse_count >= 6
    assert cc01.production_connected is False


def test_phase_candidates_no_new_c3_this_phase():
    cands = phase_core_candidates()
    assert all(c.classification != "C3" for c in cands)
    assert any(c.id == "CC-03" and c.classification == "C1" for c in cands)


def test_mandatory_phase_report_structure():
    report = build_mandatory_phase_report(
        phase_id="test",
        golden={"overall": "PASS", "pass_count": 6, "total": 6},
    )
    d = report.to_dict()
    assert "current_problem_track" in d
    assert "future_core_track" in d
    assert "existing_core_usage" in d
    assert report.policy_adoption == "ADOPT_WITH_LIMITS"


def test_anti_overengineering_max_one_c3():
    rules = anti_overengineering_rules()
    assert any("Max 1" in r for r in rules)


def test_policy_summary_includes_operating_model():
    summary = policy_summary_for_harnesses()
    assert summary["policy_version"] == "1.1-llm-centered"
    assert "operating_model" in summary


def test_run_integration():
    result = run_defensive_core_discovery_policy_integration(fetch_live_baseline=False)
    assert result["production_changes"] == []
    assert result["agent_changes"] == []
    assert result["policy_adoption"] in ("ADOPT_WITH_LIMITS", "DEFER")
    assert result["integration_status"] == "IMPLEMENTED"
    assert "CONTINUE" in result["phase_decisions"]


def test_phase_forbidden_and_success_criteria():
    from ai_tool.defensive_core_discovery_policy import (
        normal_development_operating_model,
        phase_forbidden_actions,
        phase_success_criteria,
    )

    assert len(phase_forbidden_actions()) >= 5
    assert len(phase_success_criteria()) >= 7
    assert "track_a" in normal_development_operating_model()
