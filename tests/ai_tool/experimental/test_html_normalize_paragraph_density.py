"""Tests for paragraph-density production normalization."""
from __future__ import annotations

from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence

OSAKA_WIKIDATA_INFobox = """
<html><head><title>大阪市 - Wikipedia</title></head><body>
<div id="mw-content-text"><div class="mw-parser-output">
<table class="infobox infobox_v2">{"wt":"[[1938年]]"},"総人口":{"wt":"2,817,627"}}</table>
<p>大阪市（おおさかし）は、大阪府中部に位置する市。</p>
<p>2024年の総人口は2,817,627人である。</p>
</div></div></body></html>
"""

NAV_ONLY = """
<html><body><nav>メインメニュー sidebar jump to content</nav></body></html>
"""


def test_osaka_infobox_fixture_population_in_main_text():
    out = normalize_html_to_evidence(OSAKA_WIKIDATA_INFobox)
    assert "2,817,627" in out["main_text"] or "2817627" in out["main_text"].replace(",", "")
    assert out["quality"]["fact_ready"] is True
    assert '"wt"' not in out["main_text"]
    assert out["quality"]["extraction_method"].startswith("paragraph_density")


def test_nav_only_no_fact_ready():
    out = normalize_html_to_evidence(NAV_ONLY)
    assert out["quality"]["fact_ready"] is False
