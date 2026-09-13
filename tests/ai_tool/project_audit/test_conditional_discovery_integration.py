"""Phase O — Conditional Facet Discovery + coverage overlay on experimental workflow."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    typed_record,
)
from ai_tool.experimental.development_assistance.phase_o_conditional_integration_harness import (
    dataflow_example,
    run_phase_o,
)
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f


def test_default_off_matches_phase_f_json_exit():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"
    assert result.stop_reason == "EARLY_EXIT_GATE"
    assert result.web_searches == 0
    assert result.coverage == {}
    assert all(
        (s.get("stage") if isinstance(s, dict) else s.stage) != "Facet Discovery"
        for s in result.stages
    )


def test_conditional_skips_json_and_does_not_route():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
        facet_discovery="conditional",
        facet_routing="relevant",
    )
    assert result.stop_reason == "EARLY_EXIT_GATE"
    assert result.web_searches == 0
    assert result.relevant_slice == {}
    rec = next(
        s
        for s in result.stages
        if (s.get("stage") if isinstance(s, dict) else s.stage) == "Facet Discovery"
    )
    assert rec.get("skipped") is True


def test_conditional_coverage_does_not_judge():
    store = ResearchStore()
    store.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    result = run_standard_workflow(
        "前に調べたAをPython 3.12で使えるか調べて",
        store=store,
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
    )
    assert result.discovery_decision.get("invoked") is True
    assert "python_version" in (result.coverage.get("required") or [])
    assert "feasible" not in result.decision_support
    assert result.decision_support.get("coverage")


def test_human_ops_is_candidate_not_required():
    from ai_tool.experimental.development_assistance.phase_n_facet_discovery_harness import robot_store

    result = run_standard_workflow(
        "これ、人間が途中で操作できる？",
        store=robot_store(),
        llm_enabled=False,
        facet_discovery="conditional",
        coverage_overlay=True,
        facet_routing="relevant",
    )
    assert "control_authority" in (result.coverage.get("candidates") or [])
    assert "control_authority" not in (result.coverage.get("required") or [])
    assert "feasible" not in result.decision_support


def test_phase_f_still_adopt_with_c3_zero():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0
    assert result["production_changes"] == 0


def test_phase_o_offline():
    result = run_phase_o()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["core_creation_gate"]["Reasoning"] == "REJECT"
    assert result["modes"]["D"]["json_ok"] is True
    assert (result["metrics"]["recall_D"] or 0) >= (result["metrics"]["recall_A"] or 0)
    assert result["metrics"]["false_leak_D"] == 0
    assert result["followup_chain"]["python_kept"] is True
    assert result["dataflow_example"]["no_feasible_key"] is True
    assert result["adoption"]["decision"] in {
        "ADOPT",
        "ADOPT_CONDITIONAL",
        "EXPERIMENTAL_RETAIN",
        "DEFER",
        "REJECT",
    }
    flow = dataflow_example()
    assert "Facet Discovery" in flow["stages"]
    assert "Decision Support" in flow["stages"]
