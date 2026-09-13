import json
import unittest

from tools.ai.llm.adapter import (
    build_clarity_messages,
    build_implement_messages,
    build_proposal_messages,
    build_research_judge_messages,
    build_web_candidate_messages,
)
from tools.ai.prompts.create import (
    CLARITY_CONTRACT,
    IMPLEMENT_CONTRACT,
    PROPOSAL_CONTRACT,
    RESEARCH_JUDGE_CONTRACT,
    WEB_CANDIDATE_CONTRACT,
)
from tools.system.config import get_llm_profile
from tools.system.tool_builder.research.local import collect_local_inventory, compact_inventory
from tools.system.tool_builder.research.web import SEARCH_QUERY_TEMPLATES, build_search_queries

from research.llm_benchmarks.environment_benchmark import (
    FORBIDDEN_ANSWERS,
    USER_REQUEST,
    contains_forbidden_answer,
)


def contract_text(contract):
    return "\n".join(
        f"{item.get('ja', '')}\n{item.get('en', '')}" for item in contract
    )


class EnvironmentResearchGuardTests(unittest.TestCase):
    def test_request_does_not_teach_the_command(self):
        self.assertFalse(contains_forbidden_answer(USER_REQUEST))
        self.assertIn("メモリ使用率", USER_REQUEST)

    def test_create_contracts_do_not_teach_the_command(self):
        for contract in (
            CLARITY_CONTRACT,
            PROPOSAL_CONTRACT,
            WEB_CANDIDATE_CONTRACT,
            IMPLEMENT_CONTRACT,
            RESEARCH_JUDGE_CONTRACT,
        ):
            self.assertFalse(contains_forbidden_answer(contract_text(contract)))

    def test_memory_search_templates_do_not_teach_the_command(self):
        self.assertIn("memory", SEARCH_QUERY_TEMPLATES)
        queries = build_search_queries(
            {"kind": "output", "question": "output 'status' の取得方法"},
            subject={"subcategory": "memory"},
            inventory={"available_commands": ["powershell", "wmic"]},
        )
        joined = "\n".join(queries)
        self.assertFalse(contains_forbidden_answer(joined))
        self.assertTrue(any("memory" in query.lower() for query in queries))

    def test_followup_missing_is_structured_into_keywords(self):
        from tools.system.tool_builder.research.web import structure_search_keywords

        keywords = structure_search_keywords(
            "total physical memory is still unconfirmed",
            subject={"subcategory": "memory"},
            inventory={"available_commands": ["powershell", "wmic"]},
        )
        joined = " ".join(keywords).lower()
        self.assertIn("physical memory", joined)
        self.assertNotIn("still unconfirmed", joined)
        self.assertFalse(contains_forbidden_answer(joined))

    def test_irrelevant_hits_are_filtered_for_memory(self):
        from tools.system.tool_builder.research.web import filter_relevant_hits

        hits = [
            {
                "title": "About the Exchange Online PowerShell V3 module",
                "snippet": "Exchange Online PowerShell",
                "url": "https://learn.microsoft.com/en-us/powershell/exchange/exchange-online-powershell-v2",
            },
            {
                "title": "Win32_OperatingSystem class",
                "snippet": "FreePhysicalMemory and physical memory reported in kilobytes",
                "url": "https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem",
            },
        ]
        filtered = filter_relevant_hits(
            hits,
            keywords=["total physical memory", "physical memory"],
            subject={"subcategory": "memory"},
        )
        self.assertEqual(filtered["dropped_count"], 1)
        self.assertEqual(filtered["kept_count"], 1)
        self.assertIn("Win32_OperatingSystem", filtered["hits"][0]["title"])

    def test_web_candidate_contract_includes_empty_search_restart(self):
        ids = {item.get("id") for item in WEB_CANDIDATE_CONTRACT}
        self.assertIn("empty_search_restart", ids)
        self.assertIn("exploration_hints", ids)
        compact = compact_inventory(collect_local_inventory("memory"))
        self.assertIn("powershell", compact["available_commands"])
        self.assertFalse(contains_forbidden_answer(str(compact)))

    def test_proposal_prompt_does_not_include_answer(self):
        messages = build_proposal_messages(
            {
                "target_request": USER_REQUEST,
                "structure_hint": {
                    "note": "参考は配置と戻り値の形だけ。取得コマンドはここにない。",
                },
            }
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertFalse(contains_forbidden_answer(joined))

    def test_implement_prompt_without_findings_does_not_include_answer(self):
        messages = build_implement_messages(
            {
                "target_request": USER_REQUEST,
                "usable_findings": [],
            }
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertFalse(contains_forbidden_answer(joined))

    def test_web_candidate_prompt_without_hits_does_not_include_answer(self):
        messages = build_web_candidate_messages(
            {
                "search_results": [],
                "inventory": {"available_commands": ["powershell"]},
            }
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertFalse(contains_forbidden_answer(joined))

    def test_web_candidate_prompt_includes_followup_contract(self):
        messages = build_web_candidate_messages(
            {
                "search_results": [],
                "inventory": {"available_commands": ["powershell"]},
                "followup_questions": ["total physical memory is still unconfirmed"],
            }
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertIn("followup_questions", joined)
        self.assertIn("prior_failures", joined)
        self.assertIn("verify one of those gaps", joined)

    def test_followup_search_uses_question_not_answer(self):
        queries = build_search_queries(
            {
                "kind": "output",
                "question": "メモリ使用率の取得方法",
                "followup": True,
            },
            subject={"subcategory": "memory"},
            inventory={"available_commands": ["powershell"]},
        )
        joined = "\n".join(queries)
        self.assertFalse(contains_forbidden_answer(joined))
        self.assertTrue(any("メモリ使用率" in query for query in queries))

    def test_clarity_prompt_does_not_include_answer(self):
        from tools.ai.tool_builder.clarity import create_clarity_materials

        messages = build_clarity_messages(
            create_clarity_materials("メモリを取得するToolを作って"),
            profile=get_llm_profile("qwen3_8b"),
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertFalse(contains_forbidden_answer(joined))
        self.assertIn("調査しない", joined)
        self.assertNotIn("usable_findings", joined)

    def test_judge_prompt_does_not_include_answer(self):
        messages = build_research_judge_messages(
            {
                "target_request": USER_REQUEST,
                "output": ["status"],
                "usable_findings": [
                    {
                        "command": "powershell",
                        "sample": ["Sum      : 68719476736", "Property : Capacity"],
                    }
                ],
            },
            profile=get_llm_profile("qwen3_8b"),
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertFalse(contains_forbidden_answer(joined))
        self.assertIn("satisfies_request", joined)
        self.assertIn("キー名ではなく", joined)
        self.assertIn("status / value / result", joined)
        self.assertIn("そのまま missing にコピーしない", joined)
        self.assertIn("方法だけを示す表現は禁止", joined)
        self.assertIn("計測対象", joined)
        self.assertIn("不足ラベル", joined)
        self.assertIn("verify_failure_missing", joined)
        self.assertIn("コマンドやスクリプト", joined)

    def test_state_contract_does_not_teach_the_command(self):
        from tools.ai.prompts.state import STATE_CONTRACT, STATE_QUERY_CONTRACT
        from tools.system.llm_failure_memory import load_environment_case

        text = contract_text(STATE_CONTRACT) + contract_text(STATE_QUERY_CONTRACT)
        self.assertFalse(contains_forbidden_answer(text))
        case = load_environment_case("persist_memory_usage_status")
        self.assertFalse(contains_forbidden_answer(json.dumps(case, ensure_ascii=False)))
        self.assertEqual(case["rounds"][0]["question"], "statusの単位は？")
        self.assertNotIn("メモリ使用率", case["rounds"][0]["question"])
        baseline = load_environment_case("persist_status_unit_baseline")
        self.assertFalse(
            contains_forbidden_answer(json.dumps(baseline, ensure_ascii=False))
        )
        self.assertEqual(baseline["rounds"][0]["question"], "statusの単位は何ですか？")
        self.assertNotIn("メモリ使用率", baseline["rounds"][0]["question"])
        self.assertEqual(
            baseline["state"]["decisions"][0]["value"],
            "Windowsのメモリ使用率",
        )
        ambiguous = load_environment_case("persist_unit_ambiguous")
        question = ambiguous["rounds"][0]["question"]
        self.assertEqual(question, "この値の単位は？")
        for token in ("status", "メモリ", "使用率"):
            self.assertNotIn(token, question)
        materials = json.dumps(
            ambiguous["rounds"][0]["materials"], ensure_ascii=False
        )
        self.assertIn("43.2", materials)
        self.assertNotIn("メモリ", materials)
        self.assertNotIn("使用率", materials)
        gap_case = load_environment_case("persist_unit_gap")
        question = gap_case["final"]["question"]
        self.assertEqual(question, "この値の単位は？")
        for token in ("status", "メモリ", "使用率"):
            self.assertNotIn(token, question)
        joined = "\n".join(item["question"] for item in gap_case["distractors"])
        for token in ("status", "メモリ", "使用率", "43.2", "%"):
            self.assertNotIn(token, joined)

    def test_insufficient_case_is_capacity_not_usage(self):
        from tools.ai.tool_builder.research_result import mark_insufficient
        from tools.system.llm_failure_memory import (
            environment_patterns,
            load_environment_case,
        )

        case = load_environment_case("insufficient_research_memory_capacity")
        self.assertEqual(case["class"], "research_misses_request")
        finding = case["research_result"]["usable_findings"][0]
        sample = "\n".join(finding["evidence"]["sample"])
        self.assertIn("Capacity", sample)
        self.assertNotIn("%", sample)
        packed = mark_insufficient(
            case["research_result"],
            case["research_result"]["usable_findings"],
            reason="搭載容量しか取れない",
        )
        self.assertFalse(packed["usable_findings"])
        self.assertEqual(len(packed["insufficient_findings"]), 1)
        patterns = environment_patterns(
            pattern_id="insufficient_research_memory_capacity"
        )
        self.assertEqual(len(patterns), 1)
        self.assertTrue(contains_forbidden_answer("Get-CimInstance Win32_OperatingSystem"))
        self.assertFalse(contains_forbidden_answer("Windows memory usage"))

    def test_diagnose_empty_code_is_llm_not_pipeline(self):
        from research.llm_benchmarks.environment_benchmark import diagnose_implement

        decision = diagnose_implement(
            error=None,
            text='{"path": "x.py", "function": "run", "code": "", "unimplemented": ["status"], "notes": ["未確認"]}',
            payload={
                "path": "x.py",
                "function": "run",
                "code": "",
                "unimplemented": ["status"],
                "notes": ["未確認"],
            },
        )
        self.assertEqual(decision["kind"], "llm_marked_unimplemented")
        self.assertFalse(decision["code_present"])

    def test_diagnose_no_json_with_python_is_pipeline(self):
        from research.llm_benchmarks.environment_benchmark import diagnose_implement

        decision = diagnose_implement(
            error="no_json",
            text="```python\ndef run():\n    import os\n    return {'status': '1'}\n```",
            payload=None,
        )
        self.assertEqual(decision["kind"], "pipeline_did_not_receive_code")

    def test_diagnose_alt_key_is_pipeline(self):
        from research.llm_benchmarks.environment_benchmark import diagnose_implement

        decision = diagnose_implement(
            error=None,
            text='{"source": "def run():\\n    return {\'status\': \'1\'}"}',
            payload={"source": "def run():\n    return {'status': '1'}"},
        )
        self.assertEqual(decision["kind"], "pipeline_did_not_receive_code")


if __name__ == "__main__":
    unittest.main()
