"""Tests for User-Facing Resolution & Source Presentation Proof."""
from __future__ import annotations

from ai_tool.experimental.conversation_resolution.candidate_builder import (
    build_candidates_from_sources,
    classify_candidate_relation,
    choose_presentation_mode,
)
from ai_tool.experimental.conversation_resolution.resolver import parse_follow_up_intent
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.web_evidence_llm_context_investigation import CONFLICT_SOURCE_A, CONFLICT_SOURCE_B
from ai_tool.web_research_user_facing_resolution_proof import (
    make_mock_resolution_chat_fn,
    proof_cases,
    run_proof_case,
    run_web_research_user_facing_resolution_proof,
)


def test_agreement_single_mode():
    src = EvidenceSource(
        url="https://a", title="A", main_text="大阪市人口275万人", quality={"fact_ready": True}
    )
    cands = build_candidates_from_sources([src, src])
    assert classify_candidate_relation(cands) == "AGREEMENT"
    assert choose_presentation_mode(classify_candidate_relation(cands)) == "SINGLE"


def test_definition_diff_multi():
    cands = build_candidates_from_sources([CONFLICT_SOURCE_A, CONFLICT_SOURCE_B])
    rel = classify_candidate_relation(cands)
    assert rel == "DEFINITION_DIFF"
    assert choose_presentation_mode(rel) in ("MULTI", "UNRESOLVED")


def test_follow_up_intents():
    assert parse_follow_up_intent("Aの方を採用して") == "ADOPT_A"
    assert parse_follow_up_intent("元ページを見せて") == "SHOW_SOURCE"
    assert parse_follow_up_intent("比較して") == "COMPARE"


def test_proof_cases_minimum():
    assert len(proof_cases()) >= 6


def test_proof_case_agreement():
    case = next(c for c in proof_cases() if c.case_id == "PR-C01")
    r = run_proof_case(case, llm_enabled=False)
    assert r["pass"] is True
    assert r["actual_mode"] == "SINGLE"


def test_proof_case_follow_up_selection():
    case = next(c for c in proof_cases() if c.case_id == "PR-C03")
    r = run_proof_case(case, llm_enabled=False)
    assert r["pass"] is True
    assert any(fu["result"].get("selected_candidate_id") for fu in r["follow_ups"])


def test_proof_run_all_offline():
    result = run_web_research_user_facing_resolution_proof(
        chat_fn=make_mock_resolution_chat_fn(),
        model="mock",
        llm_enabled=False,
        fetch_live_baseline=False,
    )
    assert result["production_changes"] == []
    assert result["decision"] in ("RECORD", "INVESTIGATE", "STOP_NO_CHANGE")
    assert int(result["pass_count"].split("/")[0]) >= 4
