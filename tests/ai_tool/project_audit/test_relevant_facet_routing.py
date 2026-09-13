"""Phase M — relevant facet routing into experimental Standard Workflow."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.phase_m_relevant_facet_routing_harness import (
    existing_workflow_audit,
    run_phase_m,
    seeded_store,
)
from ai_tool.experimental.development_assistance.relevant_facet_router import (
    route_relevant_facets,
    select_relevant_facets,
)
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow


def test_m1_audit_records_insertion_and_default_off():
    audit = existing_workflow_audit()
    assert audit["1_requirement_facets_generated"]["robot_facets_emitted"] is False
    assert audit["2_research_reuse_searches"]["robot_facet_keys"] is False
    assert audit["4_facet_records_usable"]["default_mode"] == "off"
    assert "Decision Support" in audit["insertion_point"]


def test_router_is_not_a_truth_judge():
    store = seeded_store()
    slice_ = route_relevant_facets(
        "Dashboardとの通信を切断すれば、人間がPolyScopeから操作を安全に再開できるか？",
        list(store.records),
        mode="relevant",
    )
    assert "transport" in slice_.facet_ids
    assert "human_handoff" in slice_.facet_ids
    item = next(i for i in slice_.items if i.facet_id == "transport")
    assert item.conflicts
    assert item.evidence
    assert "verdict" not in item.to_dict()


def test_m6_8_gate_skips_routing():
    result = run_standard_workflow(
        "JSONを検証するToolを作りたい。",
        llm_enabled=False,
        facet_routing="relevant",
    )
    assert result.stop_reason == "EARLY_EXIT_GATE"
    assert result.web_searches == 0
    assert result.relevant_slice == {}
    assert all(
        (s.get("stage") if isinstance(s, dict) else s.stage) != "Relevant Facet Routing"
        for s in result.stages
    )


def test_default_off_does_not_add_routing_stage():
    store = seeded_store()
    result = run_standard_workflow(
        "URScriptをURSim 5.15.2で実行できるか？",
        store=store,
        llm_enabled=False,
    )
    assert result.facet_routing == "off"
    assert result.relevant_slice == {}
    assert all(
        (s.get("stage") if isinstance(s, dict) else s.stage) != "Relevant Facet Routing"
        for s in result.stages
    )


def test_mode_c_k7_reaches_decision_support():
    store = seeded_store()
    req = (
        "URSimをAgentから操作したあと、Dashboardとの通信を切断すれば、"
        "人間がPolyScopeから安全に操作を再開できるToolを作ってください。"
    )
    result = run_standard_workflow(req, store=store, llm_enabled=False, facet_routing="relevant")
    ids = set(result.relevant_slice.get("facet_ids") or [])
    assert {"transport", "control_authority", "operational_mode", "operational_mode_source", "human_handoff"} <= ids
    blob = str(result.decision_support).lower()
    assert "tcp disconnect does not clear" in blob
    assert result.decision_support.get("slice_factors")


def test_slice_keeps_envelope_not_facet_id_only():
    store = seeded_store()
    result = run_standard_workflow(
        "Dashboardとの通信を切断すれば、人間がPolyScopeから操作を安全に再開できるか？",
        store=store,
        llm_enabled=False,
        facet_routing="relevant",
    )
    mode_src = next(i for i in result.relevant_slice["items"] if i["facet_id"] == "operational_mode")
    assert mode_src["value"] == "AUTOMATIC"
    assert mode_src["pulled_with"] == "operational_mode_source"
    transport = next(i for i in result.relevant_slice["items"] if i["facet_id"] == "transport")
    assert transport["evidence"]
    assert transport["conflicts"]
    assert transport["version"]
    assert transport["provenance"]


def test_phase_m_offline_no_new_core():
    result = run_phase_m()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["core_creation_gate"]["Reasoning_Matrix_Graph_Core"] == "REJECT"
    assert result["adoption"]["decision"] in {
        "ADOPT",
        "EXPERIMENTAL_RETAIN",
        "RECORD",
        "DEFER",
        "REJECT",
    }
    assert (result["metrics"]["relevant_recall_C"] or 0) > (result["metrics"]["relevant_recall_A"] or 0)
    m8 = next(r for r in result["cases"] if r["id"] == "M6-8")
    assert m8["modes"]["C"]["stop_reason"] == "EARLY_EXIT_GATE"
    assert m8["modes"]["C"]["routing_stage_present"] is False


def test_select_relevant_facets_changes_with_requirement():
    a = {x["facet_id"] for x in select_relevant_facets(
        "Dashboardとの通信を切断すれば、人間がPolyScopeから操作を安全に再開できるか？",
        __import__(
            "ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures",
            fromlist=["FACET_CATALOG"],
        ).FACET_CATALOG,
    )}
    b = {x["facet_id"] for x in select_relevant_facets(
        "URScriptをURSim 5.15.2で実行できるか？",
        __import__(
            "ai_tool.experimental.development_assistance.phase_l_relevant_facet_fixtures",
            fromlist=["FACET_CATALOG"],
        ).FACET_CATALOG,
    )}
    assert "transport" in a
    assert "urscript_api" in b
    assert a != b
