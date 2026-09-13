"""Phase P — ResearchRecord → Development Session 引き継ぎ。"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.development_session import (
    DevelopmentSessionState,
    add_official_vs_third_party_conflict,
    apply_requirement,
    attach_research,
    certainty_reply,
)
from ai_tool.experimental.development_assistance.phase_n1_generalized_fixtures import (
    record_a,
    typed_record,
)
from ai_tool.experimental.development_assistance.phase_p_session_handoff_harness import run_phase_p
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from ai_tool.experimental.development_assistance.python_version_delta import parse_python_version_delta
from ai_tool.experimental.development_assistance.research_record import ResearchStore
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f


def _store_state():
    store = ResearchStore()
    store.add(typed_record(record_a(python="Python 3.12", extra_python_versions=("3.12",))))
    state = DevelopmentSessionState()
    attach_research(state, "RR-A", "A")
    return store, state


def test_default_workflow_unchanged():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"


def test_phase_f_still_adopt():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0


def test_sonogijutsu_a_binds_with_session_id_not_string_alone():
    store, state = _store_state()
    hit = classify_pointer(
        "その技術AをPython 3.12で使えるか調べて。",
        store=store,
        session=state.as_session_dict(),
    )
    assert hit.status == "BOUND"
    assert hit.bound_research_id == "RR-A"
    assert hit.guessed is False
    miss = classify_pointer(
        "その技術AをPython 3.12で使えるか調べて。",
        store=ResearchStore(),
        session={},
    )
    assert miss.status == "UNRESOLVED"


def test_mae_no_yatsu_and_sono_kankyo_unresolved_without_session():
    empty = classify_pointer("前のやつを使って", store=ResearchStore(), session={})
    assert empty.status == "UNRESOLVED"
    env = classify_pointer("その環境ならどう？", store=ResearchStore(), session={})
    assert env.status == "UNRESOLVED"


def test_bare_version_replacement_and_session_only_change():
    d1 = parse_python_version_delta("3.12ではなく3.13で。")
    assert d1.replacement_detected is True
    assert d1.replaced_from == "3.12"
    assert d1.selected == "3.13"
    d2 = parse_python_version_delta(
        "Pythonだけ3.13に変更したので確認して。",
        {"last_python": "3.12"},
    )
    assert d2.replacement_detected is True
    assert d2.replaced_from == "3.12"
    assert d2.selected == "3.13"


def test_version_replace_does_not_copy_evidence():
    store, state = _store_state()
    apply_requirement(state, "その技術AをPython 3.12で使えるか調べて。", store)
    apply_requirement(state, "Windows環境ならどう？", store)
    apply_requirement(state, "CUDA 12.3ならどう？", store)
    out = apply_requirement(state, "Pythonだけ3.13に変更したので確認して。", store)
    py = state.facets["python_version"]
    assert py.value == "3.13"
    assert py.evidence == "UNKNOWN"
    assert py.copied_from_old is False
    assert "os" in out["reusable"]
    assert "cuda" in out["reusable"]
    assert out["full_reresearch"] is False
    assert out["searches_estimate"] == 1
    assert any(h.get("value") == "3.12" for h in state.history)


def test_certainty_is_unknown_when_conflict():
    store, state = _store_state()
    add_official_vs_third_party_conflict(state)
    reply = certainty_reply("では3.13で確実に動く？", state)
    assert reply is not None
    assert reply["answer"] == "UNKNOWN"
    assert reply["feasible"] is None
    assert reply["safe"] is None
    assert reply["correct"] is None
    assert reply["conflict_kept"] is True


def test_phase_p_session_offline():
    result = run_phase_p()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["core_creation_gate"]["Reasoning"] == "REJECT"
    m = result["metrics"]
    assert m["researchrecord_binding_accuracy"] == 1.0
    assert m["as_is_binding_accuracy"] < m["researchrecord_binding_accuracy"]
    assert m["facet_retention"] == 1.0
    assert m["changed_facet_isolation"] == 1.0
    assert m["conflict_preservation"] == 1.0
    assert m["spec_to_code"] == 1.0
    assert m["code_to_test"] == 1.0
    assert m["test_to_reeval"] == 1.0
    assert m["unnecessary_research_suppression"] == 1.0
    assert result["pointers"]["その環境"]["without_session"] == "UNRESOLVED"
    assert result["pointers"]["前のやつ"]["without_session"] == "UNRESOLVED"
    assert result["judgment"] in {"PARTIAL_PASS", "GENERALIZED_PASS", "BLOCKED", "REJECT"}
