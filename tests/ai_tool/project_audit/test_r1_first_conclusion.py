"""第1回結論 — 総合テスト。Production と既定 Workflow は変えない。"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    apply_requirement,
    seed_from_record,
)
from ai_tool.experimental.development_assistance.phase_p7_memory_fixtures import (
    scaled_store,
)
from ai_tool.experimental.development_assistance.phase_r1_first_conclusion_harness import (
    run_r1_first_conclusion,
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


def test_scale_100_binds_a_and_keeps_slice_small():
    store = scaled_store(100)
    assert len(store.records) == 100
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    hit = classify_pointer(
        "その技術Aについて調べて。",
        store=store,
        session=state.as_session_dict(),
    )
    assert hit.status == "BOUND"
    assert hit.bound_research_id == "RR-A"
    miss = classify_pointer("その技術Aについて調べて。", store=store, session={})
    assert miss.status == "UNRESOLVED"
    assert miss.guessed is False


def test_ambiguous_python_side_does_not_guess():
    store = scaled_store(20)
    amb = classify_pointer("Pythonの方", store=store, session={})
    assert amb.status == "UNRESOLVED"
    assert amb.guessed is False
    other = classify_pointer("別の方法なら？", store=store, session={"last_research_id": "RR-A"})
    assert other.status == "UNRESOLVED"


def test_a_python_change_does_not_borrow_b():
    store = scaled_store(20)
    rec_a = next(r for r in store.records if r.research_id == "RR-A")
    state = DevelopmentSessionState()
    seed_from_record(state, rec_a)
    apply_requirement(state, "AをPython 3.13に変更して。", store)
    assert state.facets["python_version"].value == "3.13"
    assert state.facets["python_version"].evidence == "UNKNOWN"
    assert state.facets["python_version"].copied_from_old is False
    assert state.facets["os"].value == "windows"
    assert state.facets["cuda"].value == "12.3"
    assert "ursim" not in state.facets


def test_r1_first_conclusion_offline():
    result = run_r1_first_conclusion()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["core_creation_gate"]["dump_all_to_llm"] == "REJECT"
    assert result["core_creation_gate"]["memory_slice_as_core"] == "REJECT_NOW"
    assert result["judgment"] in {"PASS", "PARTIAL_PASS", "FAIL", "EXPERIMENTAL"}
    assert result["metrics"]["memory_100"] > result["metrics"]["memory_5"]
    assert result["metrics"]["llm_slice_100"] <= 10
    assert result["metrics"]["llm_slice_100"] == result["metrics"]["llm_slice_5"]
    assert result["metrics"]["search_enough"] == 0
    assert result["item_results"]["1_scale"] == "PASS"
    assert result["item_results"]["6_isolation"] == "PASS"
    assert result["item_results"]["7_llm_reduce"] == "PASS"
    assert result["item_results"]["8_search_min"] == "PASS"
    assert result["cursor_agent_split"]["implemented"] is False
    assert result["impl"]["overwrote_liba_demo"] is False
    assert result["first_conclusion"]["総合判定"] == result["judgment"]
    assert result["pipeline"]["reuse_mode"] in {"no_reuse", "partial_reuse", "full_reuse"}
