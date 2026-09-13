import unittest

from tools.ai.llm.context_budget import (
    check_context_budget,
    estimate_messages_chars,
    prompt_budget_chars,
    prompt_budget_tokens,
)
from tools.ai.tool_builder.research_result import compact_prior_failures


class ContextBudgetTests(unittest.TestCase):
    def test_prompt_budget_from_profile(self):
        profile = {
            "context_limit": 4096,
            "num_predict": 2048,
        }
        self.assertEqual(prompt_budget_tokens(profile), 4096 - 2048 - 128)
        self.assertEqual(
            prompt_budget_chars(profile),
            (4096 - 2048 - 128) * 4,
        )

    def test_no_budget_when_context_limit_missing(self):
        self.assertIsNone(prompt_budget_tokens({"num_predict": 2048}))

    def test_check_context_budget_detects_overflow(self):
        profile = {"context_limit": 4096, "num_predict": 2048}
        budget = prompt_budget_chars(profile)
        messages = [{"role": "user", "content": "x" * (budget + 1)}]
        detail = check_context_budget(
            messages, profile, builder_name="build_web_candidate_messages"
        )
        self.assertIsNotNone(detail)
        self.assertEqual(detail["kind"], "context_overflow")
        self.assertGreater(detail["estimated_chars"], detail["budget_chars"])
        self.assertEqual(detail["builder"], "build_web_candidate_messages")

    def test_check_context_budget_ok_under_budget(self):
        profile = {"context_limit": 4096, "num_predict": 2048}
        messages = [{"role": "system", "content": "a"}, {"role": "user", "content": "b"}]
        self.assertIsNone(check_context_budget(messages, profile))

    def test_estimate_messages_chars_breakdown(self):
        messages = [
            {"role": "system", "content": "abc"},
            {"role": "user", "content": "de"},
        ]
        total, breakdown = estimate_messages_chars(messages)
        self.assertEqual(total, 5)
        self.assertEqual(breakdown["system"], 3)
        self.assertEqual(breakdown["user"], 2)


class CompactPriorFailuresTests(unittest.TestCase):
    def test_truncates_finding_and_error_but_keeps_command_and_args(self):
        long_cmd = "Get-WmiObject -Class Win32_OperatingSystem | " + ("x" * 300)
        research = {
            "unresolved": [
                {
                    "question": "q" * 200,
                    "finding": "f" * 300,
                    "evidence": {
                        "command": "powershell",
                        "args": ["-Command", long_cmd],
                        "error": "e" * 300,
                    },
                }
            ],
            "insufficient_findings": [],
        }
        prior = compact_prior_failures(research)
        self.assertEqual(len(prior), 1)
        item = prior[0]
        self.assertEqual(item["command"], "powershell")
        self.assertEqual(item["args"][1], long_cmd)
        self.assertLessEqual(len(item["finding"]), 201)
        self.assertLessEqual(len(item["error"]), 201)
        self.assertLessEqual(len(item["question"]), 121)


if __name__ == "__main__":
    unittest.main()
