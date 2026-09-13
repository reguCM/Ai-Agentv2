import unittest

from tools.ai.llm.adapter import build_web_candidate_messages
from tools.ai.tool_builder.research_judge import prepare_followup_research
from tools.ai.tool_builder.research_result import (
    compact_prior_failures,
    filter_rejected_candidates,
    rejected_command_list,
)
from tools.ai.tool_builder.web import web_research
from tools.system.tool_builder.research.verify import normalize_candidate
from tools.system.tool_builder.research.web import build_search_queries

from research.llm_benchmarks.research_implement_classify import inspect_missing_handoff


FAILED_FINDING = {
    "question": "How to get the memory usage rate on Windows?",
    "finding": "実環境で確認できなかった。0 で除算しようとしました。",
    "evidence": {
        "command": "powershell",
        "args": [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-WmiObject -Class Win32_OperatingSystem | Select FreePhysicalMemory,TotalPhysicalMemory",
        ],
        "sample": [],
        "error": "0 で除算しようとしました。",
    },
    "confidence": "low",
    "source": "web",
}


class MissingHandoffTests(unittest.TestCase):
    def setUp(self):
        # 旧 handoff 契約の回帰テスト。Phase 5 recall は別テストで見る。
        import os

        os.environ["AI_AGENT_MEMORY_RECALL"] = "0"

    def tearDown(self):
        import os

        os.environ.pop("AI_AGENT_MEMORY_RECALL", None)

    def test_prepare_followup_research_from_judge_missing(self):
        missing = [
            "total physical memory is still unconfirmed",
            "used memory is still unconfirmed",
        ]
        research = {"unresolved": [FAILED_FINDING], "insufficient_findings": []}
        handoff = prepare_followup_research(
            missing,
            research,
            reason="sample is empty",
        )
        self.assertEqual(len(handoff["research_items"]), 2)
        self.assertTrue(all(item["followup"] for item in handoff["research_items"]))
        self.assertEqual(handoff["followup_questions"], missing)
        self.assertEqual(len(handoff["rejected_commands"]), 1)
        self.assertEqual(len(handoff["prior_failures"]), 1)
        self.assertEqual(handoff["judge_reason"], "sample is empty")

    def test_rejected_command_list_includes_unresolved_failures(self):
        research = {"unresolved": [FAILED_FINDING], "insufficient_findings": []}
        rejected = rejected_command_list(research)
        self.assertEqual(len(rejected), 1)
        normalized = normalize_candidate(rejected[0])
        kept = filter_rejected_candidates([FAILED_FINDING["evidence"]], rejected)
        self.assertEqual(len(kept), 0)

    def test_compact_prior_failures_keeps_error_context(self):
        research = {"unresolved": [FAILED_FINDING], "insufficient_findings": []}
        prior = compact_prior_failures(research)
        self.assertEqual(len(prior), 1)
        self.assertIn("0 で除算", prior[0]["error"])

    def test_followup_search_queries_include_missing_text(self):
        missing = ["total physical memory is still unconfirmed"]
        handoff = prepare_followup_research(missing, {})
        queries = build_search_queries(
            handoff["research_items"][0],
            subject={"subcategory": "memory"},
            inventory={"available_commands": ["powershell"]},
            user_request="Windowsのメモリ使用率を取得するToolを作ってください。",
        )
        joined = "\n".join(queries)
        self.assertIn("total physical memory", joined)
        self.assertNotIn("still unconfirmed", joined)
        # 旧連結の重複 subcategory を出さない
        self.assertNotIn("memory memory", joined.lower())

    def test_web_candidate_prompt_includes_followup_questions(self):
        missing = [
            "total physical memory is still unconfirmed",
            "used memory is still unconfirmed",
        ]
        research = {"unresolved": [FAILED_FINDING], "insufficient_findings": []}
        handoff = prepare_followup_research(missing, research, reason="verify failed")
        materials = web_research(
            items=handoff["research_items"],
            search_results=[{"title": "Memory usage", "snippet": "example"}],
            inventory={"available_commands": ["powershell"]},
            rejected_commands=handoff["rejected_commands"],
            followup_questions=handoff["followup_questions"],
            prior_failures=handoff["prior_failures"],
            judge_reason=handoff["judge_reason"],
        )
        messages = build_web_candidate_messages(materials)
        joined = "\n".join(item["content"] for item in messages)
        for question in missing:
            self.assertIn(question, joined)
        self.assertIn("followup_questions", joined)
        self.assertIn("prior_failures", joined)
        self.assertIn("verify failed", joined)

    def test_inspect_missing_handoff_checks_prompt(self):
        missing = ["total physical memory is still unconfirmed"]
        handoff = prepare_followup_research(missing, {})
        materials = web_research(
            items=handoff["research_items"],
            followup_questions=handoff["followup_questions"],
        )
        inspected = inspect_missing_handoff(handoff, prompt_materials=materials)
        self.assertTrue(inspected["ok"])
        self.assertTrue(inspected["in_prompt"])


if __name__ == "__main__":
    unittest.main()
