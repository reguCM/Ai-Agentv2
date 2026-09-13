"""R2：実Research を含む記憶選択。Production と既定 Workflow は変えない。"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    apply_requirement,
    seed_from_record,
)
from ai_tool.experimental.development_assistance.phase_r2_ingest import ingest_core_store
from ai_tool.experimental.development_assistance.phase_r2_research_selection_harness import (
    run_r2_research_selection,
)
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f


def test_default_workflow_still_off():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"


def test_phase_f_still_adopt():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0


def test_pipeline_ingest_derives_facets_for_a():
    store, reports = ingest_core_store()
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    report_a = next(r for r in reports if r["research_id"] == "RR-A")
    assert report_a["facet_count_before_derive"] == 0
    assert report_a["facet_count_after_derive"] >= 4
    assert rec_a.provenance == "tda_pipeline"
    ids = {str(f.get("facet_id")) for f in rec_a.facet_records}
    assert "python_version" in ids
    assert "os" in ids
    assert "cuda" in ids
    assert "license" in ids


def test_r2_python_313_does_not_copy_312_or_borrow_b():
    store, _ = ingest_core_store()
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    apply_requirement(state, "前に調べた技術AをPython 3.13で使えるか調べて。", store)
    assert state.facets["python_version"].value == "3.13"
    assert state.facets["python_version"].evidence == "UNKNOWN"
    assert state.facets["python_version"].copied_from_old is False
    assert state.facets["os"].value == "windows"
    assert state.facets["cuda"].value == "12.3"
    assert "ursim" not in state.facets


def test_sono_gijutsu_without_a_is_unresolved_when_many_records():
    store, _ = ingest_core_store()
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    amb = classify_pointer("その技術について続けて。", store=store, session=state.as_session_dict())
    assert amb.status == "UNRESOLVED"
    assert amb.guessed is False
    assert amb.to_dict()["clarification_required"] is True


def test_r2_research_selection_offline():
    result = run_r2_research_selection()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["judgment"] in {"PASS", "PARTIAL_PASS", "FAIL"}
    assert result["item_results"]["R2-1"] == "PASS"
    assert result["item_results"]["R2-2"] == "PASS"
    assert result["item_results"]["R2-5"] == "PASS"
    assert result["item_results"]["R2-9"] in {"PASS", "PARTIAL_PASS", "SKIP"}
    assert result["metrics"]["llm_slice_100"] <= 10
    assert result["metrics"]["memory_100"] > result["metrics"]["memory_5"]
    assert result["r210"].get("implemented") is not True
    assert result["core_creation_gate"]["Production接続"] == "REJECT_NOW"
