"""Web Evidence Pipeline — search → fetch → grounding (deterministic)."""
from __future__ import annotations

from ai_tool.experimental.read_url.reader import read_url_text
from tools.system.network import general_web_search as gws
from tools.system.network.search_web import search_web
from tools.system.network.web_evidence import enrich_web_tool_result


HTML_PAGE = """
<html><head><title>Osaka</title></head><body>
<main><h1>Osaka City</h1><p>The population is approximately 2,750,000.</p></main>
</body></html>
"""


def _mock_fetch(*args, **kwargs):
    return 200, {"content-type": "text/html"}, HTML_PAGE.encode(), "https://example.com/osaka"


def test_search_enriches_snippet_and_relevance(monkeypatch) -> None:
    def fake_wiki(query, limit=5):
        return [
            {
                "title": "Osaka City Population",
                "snippet": "",
                "url": "https://example.com/osaka",
                "backend": "wikipedia",
            }
        ]

    monkeypatch.setattr(gws, "search_duckduckgo", lambda *a, **k: [])
    monkeypatch.setattr(gws, "search_wikipedia", fake_wiki)
    monkeypatch.setattr(gws, "search_wikipedia_en", lambda *a, **k: [])

    out = search_web("Osaka population", limit=3)
    assert out["hits"]
    hit = out["hits"][0]
    assert hit.get("snippet")
    assert hit.get("relevance_hint") in {"high", "medium", "low", "unknown"}
    assert out["grounding"]["web_evidence_available"] is True


def test_search_empty_grounding() -> None:
    out = enrich_web_tool_result(
        "search_web",
        {"query": "q", "hits": [], "error": "none"},
    )
    assert out["grounding"]["empty_search"] is True
    assert out["grounding"]["do_not_claim_web_verified_facts"] is True
    assert out["web_status"]["overall"] == "SEARCH_FAILED"


def test_fetch_grounding_fact_ready() -> None:
    fetched = read_url_text("https://example.com/osaka", fetch_fn=_mock_fetch)
    enriched = enrich_web_tool_result("read_url_text", fetched)
    assert fetched["quality"]["fact_ready"] is True
    assert enriched["grounding"]["prefer_main_text_for_facts"] is True
    assert enriched["grounding"]["do_not_analyze_html_structure"] is True


def test_fetch_grounding_not_fact_ready() -> None:
    fetched = read_url_text(
        "https://example.com/osaka",
        fetch_fn=lambda *a, **k: (200, {"content-type": "text/html"}, b"<html></html>", "https://example.com/osaka"),
    )
    enriched = enrich_web_tool_result("read_url_text", fetched)
    assert fetched["quality"]["fact_ready"] is False
    assert "insufficient" in enriched["grounding"]["instruction"].lower()


def test_search_fetch_evidence_pipeline(monkeypatch) -> None:
    def fake_wiki(query, limit=5):
        return [
            {
                "title": "Osaka",
                "snippet": "",
                "url": "https://example.com/osaka",
                "backend": "wikipedia",
            }
        ]

    monkeypatch.setattr(gws, "search_duckduckgo", lambda *a, **k: [])
    monkeypatch.setattr(gws, "search_wikipedia", fake_wiki)
    monkeypatch.setattr(gws, "search_wikipedia_en", lambda *a, **k: [])

    search_out = enrich_web_tool_result("search_web", search_web("Osaka population", limit=1))
    url = search_out["hits"][0]["url"]
    fetch_out = enrich_web_tool_result("read_url_text", read_url_text(url, fetch_fn=_mock_fetch))

    assert "2,750,000" in fetch_out["main_text"]
    assert fetch_out["quality"]["fact_ready"] is True
    assert search_out["grounding"]["web_evidence_available"] is True
