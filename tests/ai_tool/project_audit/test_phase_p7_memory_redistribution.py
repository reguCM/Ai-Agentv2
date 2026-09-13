"""Phase P-7〜P-12 — 記憶増量と機械的な再配分。"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    apply_requirement,
    seed_from_record,
)
from ai_tool.experimental.development_assistance.phase_p7_memory_fixtures import (
    multi_record_store,
    overlap_store,
)
from ai_tool.experimental.development_assistance.phase_p7_memory_redistribution_harness import (
    run_phase_p7_p12,
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


def test_pointer_a_does_not_guess_among_many_records():
    store = multi_record_store()
    miss = classify_pointer("その技術Aについて調べて。", store=store, session={})
    assert miss.status == "UNRESOLVED"
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    hit = classify_pointer(
        "前に調べた技術Aについて続けて。",
        store=store,
        session=state.as_session_dict(),
    )
    assert hit.status == "BOUND"
    assert hit.bound_research_id == "RR-A"


def test_windows_python_unique_and_ambiguous():
    store = overlap_store()
    hit = classify_pointer("WindowsでPython 3.12の方", store=store, session={})
    assert hit.status == "BOUND"
    assert hit.bound_research_id == "RR-WA"
    amb = classify_pointer("Windowsの方", store=store, session={})
    assert amb.status == "UNRESOLVED"
    assert amb.guessed is False


def test_cuda_change_does_not_reset_python():
    store = multi_record_store()
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    apply_requirement(state, "Python 3.13で使えるか調べて。", store)
    assert state.facets["python_version"].value == "3.13"
    assert state.facets["python_version"].evidence == "UNKNOWN"
    out = apply_requirement(state, "CUDAは12.4の環境で。", store)
    assert state.facets["python_version"].value == "3.13"
    assert state.facets["python_version"].evidence == "UNKNOWN"
    assert state.facets["cuda"].value == "12.4"
    assert state.facets["cuda"].evidence == "UNKNOWN"
    assert state.facets["cuda"].copied_from_old is False
    assert out["searches_estimate"] == 1
    assert "python_version:3.13" not in out["missing"]
    apply_requirement(state, "Pythonは3.12に戻して。", store)
    assert state.facets["python_version"].value == "3.12"
    assert state.facets["python_version"].evidence == "confirmed"
    assert state.facets["cuda"].value == "12.4"


def test_phase_p7_p12_offline():
    result = run_phase_p7_p12()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["core_creation_gate"]["memory_slice_as_core"] == "REJECT_NOW"
    assert result["judgment"] in {"PASS", "PARTIAL_PASS", "FAIL"}
    for key in ("P-7", "P-8", "P-9", "P-10", "P-11", "P-12"):
        assert result["item_results"][key] == "PASS"
    p12 = result["p12"]
    assert p12["llm_slice_facet_count"] < p12["all_memory_facet_count"]
    assert p12["cross_record_contamination"] == 0
    assert result["overlap"]["unique_ok"] is True
    assert result["overlap"]["ambiguous_unresolved"] is True
    assert "ursim" not in result["metrics"]["foreign_added"]
    assert "ros" not in result["metrics"]["foreign_added"]
