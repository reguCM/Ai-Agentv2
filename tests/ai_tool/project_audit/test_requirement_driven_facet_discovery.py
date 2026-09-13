"""Phase N — Requirement-driven Facet Discovery (no new Core)."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.facet_discovery import (
    asserts_not_a_decision,
    discover_facets,
    existing_mode_a_ids,
    plan_follow_up,
)
from ai_tool.experimental.development_assistance.goal_abstraction import abstract_goals
from ai_tool.experimental.development_assistance.phase_n_facet_discovery_harness import (
    pytorch_record_a,
    robot_store,
    run_phase_n,
)
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.research_record import ResearchStore


def test_n1_goal_abstraction_has_no_version_slots():
    goals = abstract_goals(
        "URSimをAgentから操作したあと、人間がPolyScopeから安全に操作を再開できるようにしたい。"
    ).to_dict()
    assert "level_0" in goals
    assert "version" not in goals
    assert "follow_up" not in goals
    ids = existing_mode_a_ids(
        "URSimをAgentから操作したあと、人間がPolyScopeから安全に操作を再開できるようにしたい。"
    )
    assert "control_authority" not in ids
    assert "human_handoff" not in ids


def test_n13_discovery_is_not_a_decision():
    store = robot_store()
    disc = discover_facets(
        "URScriptがURSim 5.15.2で実行可能か調べたい。",
        store,
    )
    assert asserts_not_a_decision(disc)
    blob = disc.to_dict()
    assert "verdict" not in blob
    assert "feasible" not in blob
    assert "safe" not in blob
    assert "program_state" in disc.catalog_ids()


def test_n4_follow_up_is_partial_not_full():
    store = ResearchStore()
    store.add(pytorch_record_a())
    plan = plan_follow_up(
        "さっき調べたAについて、今度はPython 3.12の場合だけもう少し調べて",
        store,
    )
    assert plan is not None
    assert plan.matched_research_id == "RR-A"
    assert plan.requested_version == "3.12"
    assert "python_version" in plan.requested_facets
    assert plan.full_reresearch is False
    assert any("3.12" in m for m in plan.missing)
    assert "cuda" in plan.reusable or "CUDA" in str(plan.reusable) or "license" in plan.reusable


def test_n6_negative_docker_excluded():
    disc = discover_facets(
        "URScriptの実行可能性だけ調べたい。Docker環境については今回は不要。",
        robot_store(),
    )
    assert "docker" in disc.excluded
    assert "urscript_api" in disc.catalog_ids()
    assert "docker" not in disc.catalog_ids()


def test_n7_comparison_two_versions():
    disc = discover_facets(
        "URSim 5.15.2と5.25.2で、この機能が使えるか比較したい。",
        robot_store(),
    )
    assert disc.comparison is True
    assert "5.15.2" in disc.versions and "5.25.2" in disc.versions
    assert "conflict" in disc.catalog_ids() or "conflict" in disc.concepts


def test_n8_not_only_safety():
    disc = discover_facets(
        "LLMだけでは安全性を判断できないので、別の検証Toolを作りたい。",
        robot_store(),
    )
    assert "llm_limitation" in disc.concepts
    assert "validation_capability" in disc.concepts
    assert "human_review" in disc.concepts
    assert disc.catalog_ids() != ["safety_state"]


def test_n12_cycle_not_dropped_by_discovery():
    req = "このロボットControllerで外部トリガによるN回Cycleを安全に実行できるか？"
    gate = assess_research_requirement(req)
    disc = discover_facets(req, robot_store())
    assert gate.decision == "RESEARCH_NOT_REQUIRED"
    assert disc.research_needed is True
    assert "cycle_controller" in disc.catalog_ids()


def test_phase_n_offline_no_new_core():
    result = run_phase_n()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["core_creation_gate"]["Reasoning_Core"] == "REJECT"
    assert result["core_creation_gate"]["Graph_Matrix_RAG_Vector"] == "REJECT"
    assert result["adoption"]["decision"] in {"REUSE", "EXPERIMENTAL", "RECORD", "DEFER", "REJECT"}
    assert (result["metrics"]["relevant_recall_C"] or 0) > (result["metrics"]["relevant_recall_A"] or 0)
    assert result["n15"]["not_always_full_search"] is True
    assert result["n15"]["prior_not_wiped"] is True
    assert all(c["C"]["not_a_decision"] for c in result["cases"])
