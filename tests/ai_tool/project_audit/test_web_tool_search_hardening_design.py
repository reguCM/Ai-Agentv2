"""Tests for Web Tool Search Hardening design probe (read-only)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ai_tool.web_tool_search_hardening_probe import (
    compare_osaka_variants,
    decompose_search_failure,
    probe_query_variant,
    run_search_hardening_probe,
)
from ai_tool.web_tool_search_hardening_probe import BackendProbeRow, QueryVariantProbe


def test_decompose_entity_missing_from_raw():
    backends = [
        BackendProbeRow("wikipedia-ja", 2, ["大阪市の不祥事", "大阪市の地名"]),
        BackendProbeRow("duckduckgo", 0, []),
    ]
    dec = decompose_search_failure(
        query="大阪市の人口",
        expected_entity="大阪市",
        backends=backends,
        pre_rank_scored=[{"score": 1, "title": "大阪市の不祥事"}],
        final_hits=[{"title": "大阪市の不祥事"}],
    )
    assert "backend_raw_quality" in dec
    assert "CONFIRMED FACT" in dec["backend_raw_quality"]


def test_decompose_ranking_when_entity_in_pool():
    backends = [BackendProbeRow("wikipedia-ja", 2, ["大阪市", "大阪市の不祥事"])]
    dec = decompose_search_failure(
        query="大阪市 人口",
        expected_entity="大阪市",
        backends=backends,
        pre_rank_scored=[{"score": 1, "title": "大阪市の不祥事"}, {"score": 4, "title": "大阪市"}],
        final_hits=[{"title": "大阪市"}],
    )
    # entity in raw and first final is entity — may not flag ranking failure
    assert dec  # non-empty decomposition


def test_probe_query_variant_mocked():
    fake_hits_good = [{"title": "大阪市", "snippet": "", "url": "http://x", "backend": "wikipedia"}]
    fake_hits_bad = [{"title": "大阪市の不祥事", "snippet": "", "url": "http://y", "backend": "wikipedia"}]

    def wiki_fn(query, limit=5):
        return fake_hits_good if " " in query else fake_hits_bad

    with patch("ai_tool.web_tool_search_hardening_probe.rw.search_duckduckgo", return_value=[]), patch(
        "ai_tool.web_tool_search_hardening_probe.rw.search_wikipedia", side_effect=wiki_fn
    ), patch("ai_tool.web_tool_search_hardening_probe.gws.search_wikipedia_en", return_value=[]), patch(
        "ai_tool.web_tool_search_hardening_probe.gws.general_web_search",
        side_effect=lambda q, **kw: {
            "query": q,
            "hits": fake_hits_good if " " in q else fake_hits_bad,
            "candidates_collected": 1,
            "error": None,
        },
    ):
        good = probe_query_variant("大阪市 人口", "osaka_space", "大阪市")
        bad = probe_query_variant("大阪市の人口", "osaka_no_particle", "大阪市")

    assert good.entity_in_raw_backend is True
    assert bad.entity_in_raw_backend is False
    cmp = compare_osaka_variants([good, bad])
    assert cmp["classification"]["ranking_only_fix_sufficient"] is False


def test_run_probe_structure():
    with patch("ai_tool.web_tool_search_hardening_probe.probe_query_variant") as pq:
        pq.return_value = QueryVariantProbe(
            query="q",
            label="lbl",
            expected_entity=None,
            query_tokens=["q"],
            backends=[],
            pre_rank_scored=[],
            final_hits=[],
            candidates_collected=0,
            tool_error=None,
            entity_in_raw_backend=None,
            entity_in_final_first=None,
            decomposition={"overall": "UNKNOWN"},
        )
        result = run_search_hardening_probe(queries=[("q", "lbl", None)])
        assert "success_criteria_mapping" in result
        assert result["success_criteria_mapping"]["S4_before_after_ready"] is True


def test_no_production_imports_for_mutation():
    src = Path(__file__).resolve().parents[3] / "ai_tool" / "web_tool_search_hardening_probe.py"
    text = src.read_text(encoding="utf-8")
    assert "registry/tools.json" not in text
    assert "agent.py" not in text


def test_phase3_artifact_optional():
    root = Path(__file__).resolve().parents[3]
    phase3 = root / "runs" / "ai_tool" / "20260828_215543_web_tool_failure_isolation_phase3" / "analysis.json"
    if phase3.is_file():
        data = json.loads(phase3.read_text(encoding="utf-8"))
        rows = data.get("search_isolation") or []
        osaka = [r for r in rows if r.get("label") in ("ja_fact_osaka_space", "ja_fact_osaka_no")]
        if len(osaka) == 2:
            space = next(r for r in osaka if r["label"] == "ja_fact_osaka_space")
            no = next(r for r in osaka if r["label"] == "ja_fact_osaka_no")
            assert space.get("first_hit_relevant") is True
            assert no.get("first_hit_relevant") is False
