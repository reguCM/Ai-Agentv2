"""Tests for read_url_text Web Evidence normalization."""
from __future__ import annotations

from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.experimental.read_url.reader import read_url_text


def _mock_fetch(status, headers, body, final_url):
    def fn(url, **kwargs):
        return status, headers, body, final_url

    return fn


SAMPLE_ARTICLE = """
<!DOCTYPE html><html><head><title>City Page</title>
<script>var x=1;</script><style>.n{display:none}</style></head>
<body><nav>Menu item</nav>
<main><h1>City</h1><p>Population is about 2,750,000 residents in 2024.</p></main>
<footer>Footer</footer></body></html>
"""

WIKI_LIKE = """
<html><head><title>大阪市 - Wikipedia</title></head><body>
<nav>long navigation</nav>
<div class="mw-parser-output"><h2 id="人口">人口</h2><p>272万人（2024年）</p></div>
</body></html>
"""


def test_html_normalize_extracts_main_text() -> None:
    out = normalize_html_to_evidence(SAMPLE_ARTICLE)
    assert "Population is about 2,750,000" in out["main_text"]
    assert "Menu item" not in out["main_text"]
    assert out["quality"]["extraction_success"] is True
    assert out["quality"]["body_reached"] is True
    assert out["quality"]["fact_ready"] is True


def test_html_normalize_strips_script_style_nav() -> None:
    out = normalize_html_to_evidence(SAMPLE_ARTICLE)
    assert "var x" not in out["main_text"]
    assert "display:none" not in out["main_text"]


def test_html_normalize_empty_body() -> None:
    out = normalize_html_to_evidence("<html><head></head><body></body></html>")
    assert out["quality"]["fact_ready"] is False


def test_html_normalize_truncated_raw_before_body() -> None:
    partial = WIKI_LIKE[:120]
    out = normalize_html_to_evidence(partial, raw_fetch_truncated=True)
    assert out["quality"]["fact_ready"] is False
    assert "raw_fetch_truncated_before_main_content" in out["quality"]["warnings"]


def test_read_url_text_returns_main_text_and_quality() -> None:
    r = read_url_text(
        "https://example.com/article",
        fetch_fn=_mock_fetch(
            200,
            {"content-type": "text/html; charset=utf-8"},
            SAMPLE_ARTICLE.encode(),
            "https://example.com/article",
        ),
    )
    assert r["ok"] is True
    assert "Population is about 2,750,000" in r["main_text"]
    assert r["content"] == r["main_text"]
    assert r["quality"]["fact_ready"] is True
    assert r["title"] == "City Page"


def test_read_url_text_plain_text_contract() -> None:
    r = read_url_text(
        "https://example.com/plain",
        fetch_fn=_mock_fetch(
            200,
            {"content-type": "text/plain"},
            b"Hello World",
            "https://example.com/plain",
        ),
    )
    assert r["main_text"] == "Hello World"
    assert r["quality"]["extraction_method"] == "plain_text"


def test_read_url_text_error_includes_evidence_fields() -> None:
    r = read_url_text("http://127.0.0.1/")
    assert r["ok"] is False
    assert r["main_text"] is None
    assert r["quality"] is None
