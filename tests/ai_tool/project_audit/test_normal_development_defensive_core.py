"""Tests for Normal Development with Defensive Core Discovery phase."""
from __future__ import annotations

from ai_tool.normal_development_defensive_core import (
    discover_track_b_candidates,
    run_normal_development_defensive_core,
    select_phase_decisions,
)


def test_no_new_c3_candidates_by_default():
    track_a = {"observation": {"eval_gap_documented": True}, "measured_production_defect": False}
    cands = discover_track_b_candidates(track_a=track_a)
    assert not any(c.classification == "C3" for c in cands)


def test_stop_no_change_when_no_production_defect():
    track_a = {"measured_production_defect": False}
    decisions = select_phase_decisions(track_a=track_a, candidates=[])
    assert "STOP_NO_CHANGE" in decisions


def test_run_phase(fetch_live=False):
    result = run_normal_development_defensive_core(fetch_live=False)
    assert result["production_changes"] == []
    assert result["production_chain_maintained"] is True
    assert result["track_b"]["new_c3_created"] is False
    assert "STOP_NO_CHANGE" in result["decisions"]
    assert "RECORD" in result["decisions"]
    assert result["phase"] == "llm_centered_web_research_architecture_adoption"
    assert len(result["what_we_did_not_build"]) >= 5
    assert result["mechanical_verification"]["answer_replacement"] == "FORBIDDEN"
    scrs = (result.get("specification") or {}).get("scr_candidates") or []
    assert any(s["id"] == "SCR-02" for s in scrs)


def test_track_b_report_rows_have_q8():
    track_a = {"observation": {"eval_gap_documented": False}, "measured_production_defect": False}
    rows = [c.to_report_row() for c in discover_track_b_candidates(track_a=track_a)]
    assert rows
    assert "LLMとの関係" in rows[0]
