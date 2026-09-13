"""Tests for Phase E — Research Reuse & Hierarchical Capability Discovery."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals, discover_capabilities
from ai_tool.experimental.development_assistance.research_audit import audit_summary
from ai_tool.experimental.development_assistance.research_record import ResearchStore, build_research_record
from ai_tool.experimental.development_assistance.research_reuse import (
    assess_reuse,
    extract_requirement_facets,
    reuse_conversation_material,
)
from ai_tool.experimental.development_assistance.research_reuse_harness import phase_e_cases, run_phase_e


def _fake_run(requirement: str, *, python: str = "Python 3.12", tech: str = "PyTorch") -> dict:
    return {
        "requirement": requirement,
        "queries": ["q1", "q2"],
        "candidates": [
            {
                "candidate_id": "TCA",
                "name": tech,
                "type": "Library",
                "version": "2.0",
                "environment": {"python": python, "cuda": "CUDA 12"},
                "license": "MIT",
                "source_category": "Official Documentation",
                "url": "https://fixture.local/docs",
                "source_title": "Docs",
                "unknowns": [],
            }
        ],
        "proposal": {"unknown": [], "conflicts": []},
        "source_urls": ["https://fixture.local/docs"],
    }


def test_structure_audit_ready_for_reuse():
    audit = audit_summary()
    assert audit["needs_dedicated_database"] is False
    assert audit["can_re_track_sources"].startswith("yes")


def test_research_record_from_run():
    rec = build_research_record(_fake_run("PyTorch GPU Tool"))
    assert rec.research_id.startswith("RR-")
    assert rec.version_facts
    assert rec.sources


def test_full_reuse_same_requirement():
    store = ResearchStore()
    run = _fake_run("Polars CSV Tool", tech="Polars", python="Python 3.9+")
    store.add_from_run(run)
    facets = extract_requirement_facets("Polars CSV Tool")
    a = assess_reuse(facets, store)
    assert a.mode == "full_reuse"
    assert a.searches_saved >= 1


def test_partial_reuse_python_version_shift():
    store = ResearchStore()
    checked = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    store.add_from_run(_fake_run("PyTorch GPU", python="Python 3.12"), checked_at=checked)
    facets = extract_requirement_facets(
        "PyTorch GPU Python 3.13 CUDA 12",
        user_constraints={"python": "Python 3.13", "cuda": "CUDA 12"},
    )
    a = assess_reuse(facets, store)
    assert a.mode == "partial_reuse"
    assert "python" in a.missing_fields
    assert "cuda" in a.reusable_fields or "license" in a.reusable_fields


def test_no_reuse_unrelated():
    store = ResearchStore()
    store.add_from_run(_fake_run("Polars", tech="Polars"))
    facets = extract_requirement_facets("JSONファイルを読み込むTool")
    a = assess_reuse(facets, store)
    assert a.mode == "no_reuse"


def test_hierarchical_discovery_duplicate_guard():
    h = discover_capabilities("前回と同じ文章が来たらLLMに渡さないToolを作りたい")
    assert h.goals.level_1
    assert h.goals.level_2
    names = {d.name for d in h.derived_capabilities}
    assert "Duplicate Guard" in names or "Context Reuse" in names
    assert any(d.decision == "REJECT" for d in h.derived_capabilities) or h.rejected_ideas


def test_reuse_material_not_ground_truth():
    store = ResearchStore()
    store.add_from_run(_fake_run("Polars"))
    facets = extract_requirement_facets("Polars CSV")
    a = assess_reuse(facets, store)
    text = reuse_conversation_material(a, store)
    assert "無条件" in text or "材料" in text or "以前" in text


def test_phase_e_cases_count():
    assert len(phase_e_cases()) == 6


def test_run_phase_e_offline():
    result = run_phase_e(llm_enabled=False)
    assert result["total"] == 6
    assert result["pass_count"] >= 5
    assert result["core_discovery"]["c3_implemented"] == 0
    assert result["production_changes"] == 0
    assert result["research_reuse_summary"]["partial_reuse"] >= 1
