"""Tests for Web Tool Failure Diagnosis Automation Phase 4."""
from __future__ import annotations

import json
from pathlib import Path

from ai_tool.web_tool_failure_diagnosis_phase4 import (
    ObservationBundle,
    diagnose,
    engine_status,
    generate_proposals,
    observation_from_live_trace,
    observation_from_search_row,
    run_failure_diagnosis,
)


def _fixture_case_b() -> dict:
    root = Path(__file__).resolve().parents[3]
    path = root / "runs" / "ai_tool" / "20260828_214841_web_tool_practical_evaluation_phase2" / "case_B_live_phase2.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "case_id": "B",
        "user_request": "検索して、見つかったページの内容を読んで説明してください。",
        "selected_tools": ["search_web"],
        "tool_call_count": 1,
        "tool_arguments": [{"query": "大阪市の人口"}],
        "tool_results": [{"hits": [{"title": "大阪市の不祥事", "relevance_hint": "low"}], "query": "大阪市の人口"}],
        "final_answer": "answer",
        "prompt_variant": "minimal",
    }


def test_deterministic_fetch_not_executed():
    obs = ObservationBundle(
        execution_id="test:fetch",
        source="unit",
        user_intent_markers=["読んで"],
        tool_calls={"search_web": 1, "read_url_text": 0},
        tool_selection_trace=["search_web"],
        agent_blocked={"fetch": False},
    )
    d1 = diagnose(obs)
    d2 = diagnose(obs)
    assert [x.to_dict() for x in d1] == [x.to_dict() for x in d2]
    assert any(x.diagnosis_id == "fetch_not_executed" for x in d1)
    dx = next(x for x in d1 if x.diagnosis_id == "fetch_not_executed")
    assert dx.classification == "TOOL_SELECTION"
    assert dx.confidence == "HIGH"
    assert dx.deterministic is True
    assert any(e["cause"] == "Agent blocked fetch" for e in dx.eliminated_causes)


def test_fetch_not_executed_unknown_without_trace():
    obs = ObservationBundle(
        execution_id="test:fetch_unknown",
        source="unit",
        user_intent_markers=["読んで"],
        tool_calls={"search_web": 1, "read_url_text": 0},
        tool_selection_trace=None,
        agent_blocked={"fetch": False},
    )
    dx = diagnose(obs)
    fetch_dx = [x for x in dx if x.diagnosis_id == "fetch_not_executed"]
    assert fetch_dx
    assert "tool_selection_trace" in fetch_dx[0].missing_observations
    assert fetch_dx[0].confidence == "UNKNOWN"


def test_wrong_search_result_high_when_backend_has_entity():
    obs = observation_from_search_row(
        {
            "query": "大阪市の人口",
            "label": "ja_fact_osaka_no",
            "expected_entity": "大阪市",
            "per_backend": {"wikipedia-ja": [{"title": "大阪市"}]},
            "post_rank_hits": [{"title": "大阪市の不祥事", "relevance_hint": "low"}],
            "first_hit_relevant": False,
        }
    )
    dx = diagnose(obs)
    wrong = [x for x in dx if x.diagnosis_id == "wrong_search_result"]
    assert wrong
    assert wrong[0].confidence == "HIGH"
    assert wrong[0].knowledge_type == "CONFIRMED_FACT"


def test_fact_ready_false_diagnosis():
    obs = ObservationBundle(
        execution_id="test:fetch_quality",
        source="unit",
        tool_calls={"read_url_text": 1},
        fetch_ok=True,
        fetch_fact_ready=False,
        fetch_main_text_len=1008,
        fetch_warnings=["main_text_looks_like_boilerplate_or_metadata"],
    )
    dx = diagnose(obs)
    assert any(x.diagnosis_id == "fact_ready_false" for x in dx)


def test_hallucinated_number_requires_empty_search():
    obs = ObservationBundle(
        execution_id="test:hallucination",
        source="unit",
        empty_search_in_trace=True,
        search_hit_count=0,
        answer_has_numeric_claim=True,
        answer_has_uncertainty=False,
        final_answer="約275万人",
    )
    dx = diagnose(obs)
    assert any(x.diagnosis_id == "hallucinated_number" for x in dx)


def test_proposals_require_human_review():
    obs = ObservationBundle(
        execution_id="test:prop",
        source="unit",
        user_intent_markers=["読んで"],
        tool_calls={"search_web": 1},
        tool_selection_trace=["search_web"],
        agent_blocked={"fetch": False},
    )
    dx = diagnose(obs)
    props = generate_proposals(dx)
    assert props
    assert all(p.human_review_required for p in props)


def test_live_trace_case_b_integration():
    case = _fixture_case_b()
    obs = observation_from_live_trace(case, source="integration")
    dx = diagnose(obs)
    ids = {d.diagnosis_id for d in dx}
    assert "fetch_not_executed" in ids
    assert "wrong_search_result" in ids


def test_run_failure_diagnosis_structure():
    result = run_failure_diagnosis()
    assert "observations" in result
    assert "diagnoses" in result
    assert "proposals" in result
    assert "human_review_packet" in result
    assert result["engine_metadata"]["llm_assisted_in_phase4"] is False


def test_engine_status_partial_or_pass():
    result = run_failure_diagnosis()
    status = engine_status(result)
    assert status["deterministic"] is True
    assert status["status"] in ("PASS", "PARTIAL")


def test_no_production_mutation_constants():
    """Safety: diagnostic module must not reference production mutation targets."""
    import ai_tool.web_tool_failure_diagnosis_phase4 as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "registry/tools.json" not in src
    assert "SYSTEM_PROMPT" not in src
    assert "agent.py" not in src
    assert mod.__doc__ is not None and "no auto-fix" in mod.__doc__.lower() or "no production" in mod.__doc__.lower()
