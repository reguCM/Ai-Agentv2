"""judge_select_method 孤立ベンチの単体テスト。LLM は呼ばない。"""

import json
from pathlib import Path

from research.llm_benchmarks.judge_select_method_classify import (
    GRADE_CORRECT,
    GRADE_FAIL,
    GRADE_OVER_ACCEPT,
    GRADE_WRONG_REJECT,
    finding_labels,
    inspect_judge_select_method,
)
from tools.system.llm_failure_memory import load_environment_case


CASE_ID = "judge_select_method_memory_usage"


def _load():
    return load_environment_case(CASE_ID)


class TestCaseStructure:
    def test_case_loads(self):
        case = _load()
        assert case is not None

    def test_five_candidates(self):
        case = _load()
        assert len(case["candidates"]) == 5

    def test_five_usable_findings(self):
        case = _load()
        findings = case["research_result"]["usable_findings"]
        assert len(findings) == 5

    def test_labels_ab_satisfy(self):
        case = _load()
        c = case["candidates"]
        assert c["A"]["satisfies"] is True
        assert c["B"]["satisfies"] is True

    def test_labels_cde_not_satisfy(self):
        case = _load()
        c = case["candidates"]
        assert c["C"]["satisfies"] is False
        assert c["D"]["satisfies"] is False
        assert c["E"]["satisfies"] is False

    def test_finding_labels_extracted(self):
        case = _load()
        labels = finding_labels(case["research_result"])
        assert set(labels.keys()) == {"A", "B", "C", "D", "E"}


class TestClassify:
    def test_accept_correct(self):
        case = _load()
        payload = {
            "satisfies_request": True,
            "reason": "sample 42 from PercentCommittedBytesInUse is memory usage percent",
            "missing": [],
            "proposed_decisions": [],
        }
        result = inspect_judge_select_method(payload, case=case)
        assert result["ok"]
        assert result["grade"] == GRADE_CORRECT

    def test_reject_all_is_wrong_reject(self):
        case = _load()
        payload = {
            "satisfies_request": False,
            "reason": "none matched",
            "missing": ["memory usage rate"],
            "proposed_decisions": [],
        }
        result = inspect_judge_select_method(payload, case=case)
        assert not result["ok"]
        assert result["grade"] == GRADE_WRONG_REJECT

    def test_no_json_is_fail(self):
        result = inspect_judge_select_method(None, "no_json", case=_load())
        assert result["grade"] == GRADE_FAIL

    def test_timeout_is_fail(self):
        result = inspect_judge_select_method(None, "timeout", case=_load())
        assert result["grade"] == GRADE_FAIL


POWER_CASE_ID = "judge_select_method_power_watt"


def _load_power():
    return load_environment_case(POWER_CASE_ID)


class TestPowerCaseStructure:
    def test_case_loads(self):
        assert _load_power() is not None

    def test_six_candidates(self):
        case = _load_power()
        assert len(case["candidates"]) == 6

    def test_abc_satisfy(self):
        c = _load_power()["candidates"]
        assert c["A"]["satisfies"] is True
        assert c["B"]["satisfies"] is True
        assert c["C"]["satisfies"] is True

    def test_def_not_satisfy(self):
        c = _load_power()["candidates"]
        assert c["D"]["satisfies"] is False
        assert c["E"]["satisfies"] is False
        assert c["F"]["satisfies"] is False

    def test_accept_correct(self):
        case = _load_power()
        payload = {
            "satisfies_request": True,
            "reason": "sample 123 from power sensor is direct watt reading",
            "missing": [],
            "proposed_decisions": [],
        }
        result = inspect_judge_select_method(payload, case=case)
        assert result["ok"]
        assert result["grade"] == GRADE_CORRECT

    def test_reject_all_wrong(self):
        case = _load_power()
        payload = {
            "satisfies_request": False,
            "reason": "no power data",
            "missing": ["power in watts"],
            "proposed_decisions": [],
        }
        result = inspect_judge_select_method(payload, case=case)
        assert not result["ok"]
        assert result["grade"] == GRADE_WRONG_REJECT
