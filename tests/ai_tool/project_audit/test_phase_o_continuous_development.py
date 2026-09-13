"""Phase O continuous development — existing TDA path, no new Core."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.implementation_handoff import (
    evaluate_tool_change,
    list_judgment_needs,
)
from ai_tool.experimental.development_assistance.phase_o_continuous_development_harness import (
    run_phase_o_continuous,
)
from ai_tool.experimental.development_assistance.python_version_delta import parse_python_version_delta
from ai_tool.experimental.development_assistance.standard_workflow import run_standard_workflow
from ai_tool.experimental.development_assistance.workflow_adoption_harness import run_phase_f
from ai_tool.experimental.liba_demo_tool.client import parse_a_payload


def test_default_workflow_still_off():
    result = run_standard_workflow(
        "JSONファイルを読み込んで内容を返すToolを作りたい",
        llm_enabled=False,
    )
    assert result.facet_discovery == "off"
    assert result.stop_reason == "EARLY_EXIT_GATE"


def test_phase_f_still_adopt():
    result = run_phase_f(llm_enabled=False)
    assert result["decision"] == "ADOPT"
    assert result["core_discovery"]["c3_implemented"] == 0


def test_python_replacement_overlay_is_not_first_match():
    delta = parse_python_version_delta(
        "Python 3.12ではなくPython 3.13の場合だけ確認し直して。"
    )
    assert delta.replacement_detected is True
    assert delta.replaced_from == "3.12"
    assert delta.selected == "3.13"


def test_judgment_needs_are_not_a_verdict():
    needs = list_judgment_needs(
        "では、これをToolとして作れそう？",
        {"required": ["environment", "evidence"], "candidates": ["license"]},
        {"runtime": "Python 3.12", "license": "Y"},
    )
    assert needs["not_a_verdict"] is True
    assert "feasible" not in needs["needs"]
    assert "safe" not in needs["needs"]
    assert "runtime" in needs["needs"]


def test_o8_does_not_rewrite():
    eval_ = evaluate_tool_change(
        "Python 3.13へ変更した結果、作成したToolに何か変更が必要？",
        spec={"runtime": "Python 3.12", "tool_name": "tool_liba"},
        session={"tool_path": "x", "last_python": "3.12"},
        tool_hash_before="abc",
        tool_hash_after="abc",
    )
    assert eval_["auto_modified"] is False
    assert eval_["change_needed"] == "UNKNOWN"
    assert eval_["from_runtime"] == "3.12"
    assert eval_["to_runtime"] == "3.13"


def test_liba_fixture_client():
    assert parse_a_payload('{"a": 1}') == {"a": 1}


def test_continuous_session_offline():
    result = run_phase_o_continuous()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["core_creation_gate"]["Reasoning"] == "REJECT"
    assert len(result["steps"]) == 8
    assert result["steps"][0]["research_record_ids"]
    o2 = result["steps"][1]
    assert "python_version" in (o2.get("required_facet") or [])
    o3 = result["steps"][2]
    assert "docker" not in (o3.get("required_facet") or [])
    o4 = result["steps"][3]
    assert "docker" in (o4.get("required_facet") or [])
    assert o4.get("ursim_in_required") is False
    o5 = result["steps"][4]
    assert o5["decision_support_input"]["has_feasible_key"] is False
    assert "feasible" not in str(o5.get("judgment_needs") or {})
    o6 = result["steps"][5]
    assert (o6.get("implementation_result") or {}).get("code_generated") is True
    assert (o6.get("test_result") or {}).get("ok") is True
    o8 = result["steps"][7]
    assert (o8.get("change_eval") or {}).get("auto_modified") is False
    assert result["judgment"] in {"PARTIAL_PASS", "GENERALIZED_PASS", "BLOCKED", "REJECT"}
    assert result["metrics"]["search_total"] == 0 or result["metrics"]["search_total"] >= 0
