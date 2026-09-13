"""Tests for Tool Development Assistance Experimental PoC."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.fixtures import tda_evaluation_cases
from ai_tool.experimental.development_assistance.followup import parse_tda_follow_up_intent
from ai_tool.experimental.development_assistance.harness import run_tda_poc, run_tda_case
from ai_tool.experimental.development_assistance.query_generator import generate_search_queries
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.technology_candidate import (
    build_technology_candidates,
)
from ai_tool.experimental.evidence_context.packager import EvidenceSource


def test_gate_case_a_not_required():
    gate = assess_research_requirement(
        "JSONファイルを読み込むToolを作りたい",
        case_hint="TDA-A",
    )
    assert gate.decision == "RESEARCH_NOT_REQUIRED"


def test_gate_case_g_required():
    gate = assess_research_requirement(
        "Universal Robotsのロボット用コードを書くToolを作りたい",
        case_hint="TDA-G",
    )
    assert gate.decision == "RESEARCH_REQUIRED"


def test_query_generator_max_three():
    qs = generate_search_queries("PDFを解析するToolを作りたい")
    assert 1 <= len(qs) <= 3
    assert any("pdf" in q.lower() or "documentation" in q.lower() for q in qs)


def test_technology_candidate_from_source():
    src = EvidenceSource(
        url="https://github.com/example/lib",
        title="ExampleLib",
        main_text="ExampleLib v2.1. Python 3.12. License: MIT. pip install examplelib.",
        quality={"fact_ready": True},
    )
    cands = build_technology_candidates([src])
    assert len(cands) == 1
    assert cands[0].type in ("OSS", "Library", "Unknown")
    assert cands[0].version != "UNKNOWN" or "version" in cands[0].unknowns


def test_follow_up_intents():
    assert parse_tda_follow_up_intent("Bについてもっと調べて") == "RESEARCH_MORE"
    assert parse_tda_follow_up_intent("自作したい") == "BUILD_CUSTOM"
    assert parse_tda_follow_up_intent("Aを使いたい") == "SELECT_CANDIDATE"


def test_case_b_web_offline():
    spec = next(c for c in tda_evaluation_cases() if c.case_id == "TDA-B")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    assert r["pass"] is True
    assert r["sources_extracted"] >= 1


def test_case_e_version_conflict():
    spec = next(c for c in tda_evaluation_cases() if c.case_id == "TDA-E")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    assert r["pass"] is True
    assert r.get("relation") == "DEFINITION_DIFF"


def test_case_g_urscript():
    spec = next(c for c in tda_evaluation_cases() if c.case_id == "TDA-G")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    assert r["pass"] is True
    blob = str(r.get("candidates"))
    assert "URScript" in blob or "urscript" in blob.lower()


def test_case_d_custom_build():
    spec = next(c for c in tda_evaluation_cases() if c.case_id == "TDA-D")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    assert r["pass"] is True
    assert any(c.get("type") == "Custom Build" for c in r.get("candidates", []))


def test_poc_run_offline():
    result = run_tda_poc(llm_enabled=False, fetch_live_baseline=False)
    assert result["production_changes"] == []
    assert result["golden_pass"] is True
    assert int(result["pass_count"].split("/")[0]) >= 5
    assert result["decision"] in ("CONTINUE", "INVESTIGATE", "STOP_NO_VALUE")
