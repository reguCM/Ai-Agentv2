"""R3：最小開発ループ。Production と既定 Workflow は変えない。"""
from __future__ import annotations

from ai_tool.experimental.development_assistance.development_session import DevelopmentSessionState
from ai_tool.experimental.development_assistance.phase_r3_min_loop_harness import run_r3_min_dev_loop
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


def test_session_has_awaiting_human_review():
    state = DevelopmentSessionState()
    assert state.awaiting_human_review is False
    state.awaiting_human_review = True
    assert state.as_session_dict()["awaiting_human_review"] is True
    assert "last_test_result" in state.as_session_dict()


def test_r3_min_dev_loop_offline():
    result = run_r3_min_dev_loop()
    assert result["production_changes"] == 0
    assert result["new_c3"] == 0
    assert result["standard_workflow_default_discovery"] == "off"
    assert result["phase_f_decision"] == "ADOPT"
    assert result["judgment"] in {"PASS", "PARTIAL_PASS", "FAIL"}
    assert result["item_results"]["R3-1"] == "PASS"
    assert result["item_results"]["R3-5"] == "PASS"
    assert result["item_results"]["R3-7"] == "PASS"
    assert result["metrics"]["llm_facets"] <= 10
    assert result["metrics"]["contamination"] == 0
    assert result["metrics"]["test_success"] == "PASS"
    assert result["metrics"]["test_fail_then"] == "PASS"
    assert result["core_creation_gate"]["Production接続"] == "REJECT_NOW"
    assert result["core_creation_gate"]["Cursor本番API"] == "REJECT_NOW"
    if result["item_results"].get("R3-14") != "SKIP":
        assert result["r314"]["production_connect"] == "REJECT_NOW"
