"""Tests for experimental extraction prototype."""
from __future__ import annotations

from ai_tool.experimental.read_url.extraction_prototype import (
    STRATEGIES,
    run_all_strategies,
    run_strategy,
    strategy_s0_production,
    strategy_s3_metadata_strip_content,
    strategy_s4_paragraph_density,
)

OSAKA_WIKIDATA_ONLY = """
<html><body><div class="mw-parser-output">
<table class="infobox">{"wt":"[[1938年]]"},"市章":{"wt":"x"}}</table>
</div></body></html>
"""

OSAKA_LIKE = """
<html><head><title>大阪市</title></head><body>
<div id="mw-content-text"><div class="mw-parser-output">
<table class="infobox">{"wt":"wikidata"}</table>
<p>Lead paragraph about the city.</p>
<h2>人口</h2><p>総人口は2,817,627人。</p>
</div></div></body></html>
"""

NAV_ONLY = """
<html><body><nav>メインメニュー sidebar jump to content</nav></body></html>
"""


def test_all_strategies_registered():
    assert len(STRATEGIES) >= 8
    assert "S0_PRODUCTION" in STRATEGIES
    assert "S3_METADATA_STRIP" in STRATEGIES


def test_s3_finds_population_on_fixture():
    r = strategy_s3_metadata_strip_content(OSAKA_LIKE, url="fixture://osaka", expect="population")
    assert r.evidence_presence["population"] is True
    assert r.evidence_presence["wikidata_boilerplate"] is False


def test_s0_fails_wikidata_center_fixture():
    r = strategy_s0_production(OSAKA_WIKIDATA_ONLY, url="fixture://osaka", expect="population")
    assert not r.evidence_presence["population"]
    assert r.evidence_presence["wikidata_boilerplate"] or r.fact_ready is False


def test_s4_paragraph_density_fixture():
    simple = """
    <html><body><main>
    <p>Intro text.</p>
    <p>総人口は2,817,627人（2024年）。</p>
    </main></body></html>
    """
    r = strategy_s4_paragraph_density(simple, url="fixture://osaka", expect="population")
    assert r.evidence_presence["population"] is True


def test_nav_fixture_no_false_population():
    for sid in ("S3_METADATA_STRIP", "S4_PARAGRAPH_DENSITY", "S0_PRODUCTION"):
        r = run_strategy(sid, NAV_ONLY, expect="none")
        assert r.evidence_presence["population"] is False


def test_run_all_strategies_count():
    rows = run_all_strategies(OSAKA_LIKE, expect="population")
    assert len(rows) == len(STRATEGIES)
