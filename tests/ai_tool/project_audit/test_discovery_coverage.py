"""Phase N+2 — Facet Discovery coverage (no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.facet_coverage import (
    asserts_coverage_not_a_decision,
    discover_coverage,
    extract_slots,
)
from ai_tool.experimental.development_assistance.phase_n2_discovery_coverage_harness import (
    _ab_store,
    _store,
    run_phase_n2,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore


def test_json_codegen_is_not_false_discovery():
    cov = discover_coverage("PythonでJSONを読むコードを書いて", _ab_store(), mode="GCR")
    assert cov.skipped is True
    assert cov.required_ids() == []
    assert asserts_coverage_not_a_decision(cov)


def test_api_paraphrase_recovered_by_alias_not_keyword():
    req = "Aの最新Versionで使えるAPIを調べて"
    k = discover_coverage(req, _ab_store(), mode="K")
    ka = discover_coverage(req, _ab_store(), mode="KA")
    assert "availability" not in k.required_ids()
    assert "version" in ka.required_ids()
    assert "api" in ka.required_ids()


def test_unresolved_environment_does_not_guess_os():
    cov = discover_coverage("その環境ならどう？", _ab_store(), mode="GCR")
    assert "その環境" in cov.unresolved
    assert "docker" not in cov.required_ids()
    assert "windows" not in cov.required_ids()


def test_bound_environment_uses_session():
    cov = discover_coverage(
        "その環境ならどう？",
        _ab_store(),
        mode="GCR",
        session={"last_research_id": "RR-A", "last_environment": "Windows RTX 3060"},
    )
    assert "その環境" not in cov.unresolved
    assert "environment" in cov.required_ids()


def test_human_ops_is_candidate_not_verdict():
    cov = discover_coverage("これ、人間が途中で操作できる？", _store("robot"), mode="GCR")
    assert "control_authority" in cov.candidate_ids()
    assert "control_authority" not in cov.required_ids()
    assert asserts_coverage_not_a_decision(cov)


def test_compare_lists_axes_not_a_choice():
    cov = discover_coverage("AとBどちらを使った方がいい？", _ab_store(), mode="GCR")
    for ax in ("target", "environment", "license", "conflict"):
        assert ax in cov.required_ids()
    assert "verdict" not in cov.to_dict()
    assert asserts_coverage_not_a_decision(cov)


def test_python_change_keeps_cuda():
    cov = discover_coverage(
        "前に調べたAについて、Python 3.12の場合だけもう少し調べて",
        _ab_store(),
        mode="GCR",
    )
    assert "python_version" in cov.required_ids() or "python_version" in cov.changed_facets
    assert cov.slots.target == "A"
    assert "cuda" in cov.keep_facets or "cuda" in cov.candidate_ids()


def test_empty_store_this_env_does_not_invent_docker():
    cov = discover_coverage("この環境で試せる？", ResearchStore(), mode="GCR")
    assert "environment" in cov.required_ids()
    assert "docker" not in cov.required_ids()
    assert "docker" in cov.unknown_ids()


def test_feasibility_phrase_is_not_a_decision():
    slots = extract_slots("この条件でToolにできそう？")
    assert slots.purpose == "feasibility_check"
    cov = discover_coverage("この条件でToolにできそう？", _ab_store(), mode="GCR")
    assert asserts_coverage_not_a_decision(cov)
    assert "feasible" not in cov.to_dict()


def test_phase_n2_offline_no_new_core():
    result = run_phase_n2()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_changed"] is False
    assert result["core_creation_gate"]["Reasoning"] == "REJECT"
    gcr = result["metrics"]["required_recall_GCR"] or 0
    k = result["metrics"]["required_recall_K"] or 0
    assert gcr >= 0.80
    assert gcr >= k
    assert result["metrics"]["false_discovery_GCR"] == 0
    assert result["followup_chain"]["last_no_decision"] is True
    assert result["followup_chain"]["python_kept"] is True
    json_rows = [r for r in result["modes"]["GCR"]["cases"] if r["miss"] == "false_discovery"]
    assert json_rows
    assert all(not r["false_discovery"] for r in json_rows)
    assert result["adoption"]["decision"] in {
        "GENERALIZED_PASS",
        "EXPERIMENTAL_RETAIN",
        "DEFER",
        "REJECT",
        "BLOCKED",
    }
