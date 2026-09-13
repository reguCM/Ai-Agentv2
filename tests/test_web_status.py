"""Unit tests for web_status and web_answer_boundary."""
from __future__ import annotations

from tools.system.network.web_answer_boundary import apply_web_answer_boundary
from tools.system.network.web_evidence import enrich_web_tool_result
from tools.system.network.web_status import WebSessionTracker, derive_fetch_status, derive_search_status


def test_search_empty_is_search_failed():
    snap = derive_search_status({"query": "q", "hits": [], "error": None})
    assert snap.overall == "SEARCH_FAILED"
    assert snap.failure_cause == "search_empty"


def test_search_hits_is_partial_not_success():
    snap = derive_search_status({"query": "q", "hits": [{"title": "a", "url": "https://x"}]})
    assert snap.layers.search == "SUCCESS"
    assert snap.overall == "PARTIAL"


def test_fetch_failed():
    snap = derive_fetch_status({"ok": False, "url": "https://x", "error": "timeout"})
    assert snap.overall == "FETCH_FAILED"
    assert snap.layers.fetch == "FAILED"


def test_fetch_success_fact_ready():
    snap = derive_fetch_status(
        {
            "ok": True,
            "main_text": "Population is about 2,750,000 residents in 2024.",
            "quality": {
                "extraction_success": True,
                "body_reached": True,
                "fact_ready": True,
                "warnings": [],
            },
        }
    )
    assert snap.overall == "SUCCESS"
    assert snap.layers.evidence == "AVAILABLE"


def test_enrich_attaches_web_status():
    out = enrich_web_tool_result("search_web", {"query": "q", "hits": []})
    assert "web_status" in out
    assert out["web_status"]["overall"] == "SEARCH_FAILED"
    assert out["grounding"]["web_status_overall"] == "SEARCH_FAILED"


def test_session_aggregate_success():
    session = WebSessionTracker()
    session.record(
        "read_url_text",
        enrich_web_tool_result(
            "read_url_text",
            {
                "ok": True,
                "main_text": "Population is about 2,750,000.",
                "quality": {
                    "extraction_success": True,
                    "body_reached": True,
                    "fact_ready": True,
                    "warnings": [],
                },
            },
        ),
    )
    assert session.aggregate()["overall"] == "SUCCESS"


def test_boundary_blocks_numeric_on_empty_search():
    session = WebSessionTracker()
    session.record("search_web", enrich_web_tool_result("search_web", {"query": "q", "hits": []}))
    out = apply_web_answer_boundary("人口は275万人です。", session)
    assert out["boundary_applied"] is True
    assert "275" not in out["answer"]
    assert out["system_notice"]


def test_boundary_allows_success():
    session = WebSessionTracker()
    session.record(
        "read_url_text",
        enrich_web_tool_result(
            "read_url_text",
            {
                "ok": True,
                "main_text": "Population 2,750,000",
                "quality": {
                    "extraction_success": True,
                    "body_reached": True,
                    "fact_ready": True,
                    "warnings": [],
                },
            },
        ),
    )
    answer = "Population is 2,750,000 per the page."
    out = apply_web_answer_boundary(answer, session)
    assert out["boundary_applied"] is False
    assert out["answer"] == answer


def test_observation_bridge_for_diagnosis():
    from tools.system.network.web_status import observation_from_web_session

    session = WebSessionTracker()
    session.record("search_web", enrich_web_tool_result("search_web", {"query": "q", "hits": []}))
    obs = observation_from_web_session(session)
    assert obs["grounding_metadata"]["web_status_overall"] == "SEARCH_FAILED"
    assert obs["empty_search_in_trace"] is True
    search_snap = derive_search_status({"query": "q", "hits": []})
    fetch_snap = derive_fetch_status(
        {
            "ok": True,
            "main_text": "Unrelated transport info only.",
            "quality": {
                "extraction_success": True,
                "body_reached": True,
                "fact_ready": False,
                "warnings": [],
            },
        }
    )
    assert search_snap.overall == "SEARCH_FAILED"
    assert fetch_snap.overall == "NO_EVIDENCE"
    assert search_snap.overall != fetch_snap.overall
