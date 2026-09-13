"""Phase N+1 — generalized Facet Discovery (no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
    plan_follow_up,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_facet_harness import (
    _store,
    run_phase_n1,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import record_a, typed_record
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore


def test_docker_does_not_pull_ursim_for_generic_a():
    store = _store()
    disc = discover_facets("前に調べたAをDockerで動かしたい。何が変わるか調べて", store)
    ids = disc.catalog_ids()
    assert "docker" in ids
    assert "ursim" not in ids
    assert "control_authority" not in ids
    assert asserts_not_a_decision(disc)


def test_python_partial_reuses_312_from_version_facts():
    store = ResearchStore()
    store.add(typed_record(record_a(python="Python 3.13", extra_python_versions=("3.12", "3.13"))))
    plan = plan_follow_up("前に調べたAをPython 3.12で使いたい。必要な変更だけ調べて", store)
    assert plan is not None
    assert plan.full_reresearch is False
    assert plan.matched_research_id == "RR-A"
    assert plan.searches_estimate == 0
    assert "python_version" in plan.reusable


def test_version_isolation_python_only():
    store = ResearchStore()
    store.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    plan = plan_follow_up("AをPython 3.13、CUDA 12.3の場合だけ再評価して。", store)
    assert plan is not None
    assert any("python 3.13" in m for m in plan.missing)
    assert not any("cuda" in m for m in plan.missing)
    assert "cuda" in plan.version_sensitive or "cuda" in plan.reusable or "cuda" in plan.requested_facets


def test_json_gate_skips_heavy_path():
    req = "JSONをPythonで読み込む方法を教えて"
    assert assess_research_requirement(req).decision == "RESEARCH_NOT_REQUIRED"
    result = run_phase_n1()
    j = next(r for r in result["cases"] if r["id"] == "J-json")
    assert j["C"]["skipped_discovery"] is True
    assert j["C"]["searches"] == 0


def test_no_decision_keys_on_hardware():
    disc = discover_facets("AをRTX 3060 12GBのWindows環境で動かせるか調べて", _store())
    blob = disc.to_dict()
    for k in ("feasible", "safe", "executable", "build"):
        assert k not in blob
    assert "hardware" in disc.catalog_ids()
    assert "os" in disc.catalog_ids()


def test_phase_n1_offline_no_new_core():
    result = run_phase_n1()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["core_creation_gate"]["Reasoning_Graph_RAG_Vector"] == "REJECT"
    assert result["adoption"]["decision"] in {
        "GENERALIZED_PASS",
        "DOMAIN_LIMITED",
        "EXPERIMENTAL_RETAIN",
        "REJECT",
    }
    assert result["adoption"]["ur_leak_on_generic_docker"] is False
    assert result["followup_chain"]["continuity"] is True
    assert (result["metrics"]["relevant_recall_C"] or 0) > (result["metrics"]["relevant_recall_A"] or 0)
    assert len(result["domains_evaluated"]) >= 6
