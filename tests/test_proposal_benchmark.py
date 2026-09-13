"""proposal_benchmark の単体テスト。LLM は呼ばない。"""

from research.llm_benchmarks.proposal_classify import (
    GRADE_COMPLETE,
    GRADE_FAIL,
    GRADE_INCOMPLETE,
    inspect_proposal,
)
from tools.system.llm_failure_memory import load_environment_case
from tools.system.tool_builder.validate.proposal_completeness import (
    validate_proposal_completeness,
)


CASE_ID = "proposal_memory_usage"


def _load():
    return load_environment_case(CASE_ID)


class TestCaseStructure:
    def test_case_loads(self):
        assert _load() is not None

    def test_expected_fields(self):
        case = _load()
        exp = case["expected"]
        assert exp["category"] == "system"
        assert "memory" in exp["subcategory_contains"]


class TestClassify:
    def test_complete_proposal(self):
        case = _load()
        payload = {
            "proposals": [
                {
                    "name": "get_memory_status",
                    "category": "system",
                    "subcategory": "memory",
                    "description": "Windows のメモリ使用率を取得する",
                    "module": "tools.system.memory.memory_status",
                    "function": "get_memory_status",
                    "output": ["status"],
                }
            ]
        }
        result = inspect_proposal(payload, case=case)
        assert result["ok"]
        assert result["grade"] == GRADE_COMPLETE

    def test_missing_module(self):
        case = _load()
        payload = {
            "proposals": [
                {
                    "name": "get_memory_status",
                    "category": "system",
                    "subcategory": "memory",
                    "function": "get_memory_status",
                    "output": ["status"],
                }
            ]
        }
        result = inspect_proposal(payload, case=case)
        assert not result["ok"]
        assert result["grade"] == GRADE_INCOMPLETE
        assert "module" in result["missing_keys"]

    def test_wrong_category(self):
        case = _load()
        payload = {
            "proposals": [
                {
                    "name": "get_memory_status",
                    "category": "network",
                    "subcategory": "memory",
                    "module": "tools.network.memory.memory_status",
                    "function": "get_memory_status",
                    "output": ["status"],
                }
            ]
        }
        result = inspect_proposal(payload, case=case)
        assert not result["ok"]
        assert result["checks"]["category_match"] is False

    def test_no_json_is_fail(self):
        result = inspect_proposal(None, "no_json", case=_load())
        assert result["grade"] == GRADE_FAIL

    def test_empty_proposals_is_fail(self):
        result = inspect_proposal({"proposals": []}, case=_load())
        assert result["grade"] == GRADE_FAIL


class TestProposalCompleteness:
    def test_complete_proposal_passes(self):
        proposal = {
            "name": "get_memory_status",
            "category": "system",
            "subcategory": "memory",
            "module": "tools.system.memory.memory_status",
            "function": "get_memory_status",
            "output": ["status"],
            "implementation_notes": ["取得方法は未確認"],
        }
        result = validate_proposal_completeness(proposal)
        assert result["ok"]
        assert not result["errors"]

    def test_placeholder_module_detected(self):
        proposal = {
            "name": "get_memory_status",
            "category": "system",
            "module": "tools.system.subcategory.filename",
            "function": "get_memory_status",
            "output": ["status"],
            "implementation_notes": ["x"],
        }
        result = validate_proposal_completeness(proposal)
        assert not result["ok"]
        fields = [e["field"] for e in result["errors"]]
        assert "module" in fields

    def test_empty_name_detected(self):
        proposal = {
            "name": "",
            "category": "system",
            "module": "tools.system.memory.memory_status",
            "function": "get_memory_status",
            "output": ["status"],
            "implementation_notes": ["x"],
        }
        result = validate_proposal_completeness(proposal)
        assert not result["ok"]
        assert any(e["field"] == "name" for e in result["errors"])

    def test_empty_function_detected(self):
        proposal = {
            "name": "get_memory_status",
            "category": "system",
            "module": "tools.system.memory.memory_status",
            "function": "",
            "output": ["status"],
            "implementation_notes": ["x"],
        }
        result = validate_proposal_completeness(proposal)
        assert not result["ok"]
        assert any(e["field"] == "function" for e in result["errors"])

    def test_template_placeholder_subject(self):
        proposal = {
            "name": "get_<SUBJECT>_status",
            "category": "system",
            "module": "tools.<CATEGORY>.<SUBCATEGORY>.<FILENAME>",
            "function": "get_<SUBJECT>_status",
            "output": ["status"],
            "implementation_notes": ["x"],
        }
        result = validate_proposal_completeness(proposal)
        assert not result["ok"]
        fields = [e["field"] for e in result["errors"]]
        assert "name" in fields
        assert "module" in fields
        assert "function" in fields

    def test_hint_is_generated(self):
        proposal = {"name": "", "category": "system", "module": "", "function": "", "output": ["status"]}
        result = validate_proposal_completeness(proposal)
        assert "修正" in result["hint"]

    def test_missing_implementation_notes(self):
        proposal = {
            "name": "x",
            "category": "system",
            "module": "tools.system.memory.x",
            "function": "x",
            "output": ["status"],
        }
        result = validate_proposal_completeness(proposal)
        assert not result["ok"]
        assert any(e["field"] == "implementation_notes" for e in result["errors"])
