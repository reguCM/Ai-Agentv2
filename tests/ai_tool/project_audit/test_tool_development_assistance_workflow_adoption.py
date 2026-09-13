"""Tests for Phase F — Standard Workflow Adoption."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.idea_preservation import IdeaCatalog
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import (
    compare_workflows,
    run_standard_workflow,
)
from ai_tool.experimental.development_assistance.workflow_adoption_harness import phase_f_cases, run_phase_f


def test_standard_workflow_early_exit_json():
    from ai_tool.experimental.development_assistance.fixtures import tda_evaluation_cases

    tda = next(c for c in tda_evaluation_cases() if c.case_id == "TDA-A")
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        tda=tda,
        llm_enabled=False,
    )
    assert result.stop_reason == "EARLY_EXIT_GATE"
    assert result.early_exit_at == "Requirement Gate"
    assert result.web_searches == 0


def test_compare_workflows_search_reduction_with_seed():
    from ai_tool.experimental.development_assistance.fixtures import tda_evaluation_cases

    by_id = {c.case_id: c for c in tda_evaluation_cases()}
    store = ResearchStore()
    run = __import__(
        "ai_tool.experimental.development_assistance.harness", fromlist=["run_tda_case"]
    ).run_tda_case(by_id["TDA-B"], mode="llm_web", llm_enabled=False)
    run["requirement"] = by_id["TDA-B"].user_requirement
    store.add_from_run(run)

    cmp = compare_workflows(
        by_id["TDA-B"].user_requirement,
        tda=by_id["TDA-B"],
        store=store,
        llm_enabled=False,
    )
    assert cmp["search_reduction"] >= 0
    assert cmp["after"]["stop_reason"] in ("EARLY_EXIT_FULL_REUSE", "PARTIAL_REUSE_WEB", "FULL_WEB_RESEARCH")


def test_idea_preservation_re_evaluable():
    catalog = IdeaCatalog()
    hits = catalog.re_evaluate_for_requirement("sandbox runner for environment verification")
    assert any("Sandbox" in h.idea for h in hits)


def test_phase_f_cases_count():
    assert len(phase_f_cases()) >= 5


def test_run_phase_f_offline():
    result = run_phase_f(llm_enabled=False)
    assert result["total"] >= 5
    assert result["pass_count"] == 6
    assert result["core_discovery"]["c3_implemented"] == 0
    assert result["production_changes"] == 0
    assert result["decision"] == "ADOPT"
