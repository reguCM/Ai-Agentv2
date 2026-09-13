import unittest

from tools.ai.tool_builder.research_result import command_key
from tools.system.tool_builder.research.progress import (
    CONTINUE,
    IMPLEMENT,
    STOP,
    evaluate_research_progress,
    normalize_missing,
)


def key(command, *args):
    return command_key(
        {"evidence": {"command": command, "args": list(args)}}
    )


class ResearchProgressTests(unittest.TestCase):
    def test_satisfies_request_implements(self):
        decision = evaluate_research_progress(
            satisfies_request=True,
            missing=[],
            previous_missing=["メモリ使用率の取得方法"],
            round_finding_keys=[key("powershell", "Get-Counter")],
            seen_keys=set(),
            stagnation=2,
            round_num=4,
        )
        self.assertEqual(decision["action"], IMPLEMENT)
        self.assertEqual(decision["reason"], "findings_complete")
        self.assertEqual(decision["stagnation"], 0)

    def test_missing_resolved_implements(self):
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=[],
            previous_missing=["メモリ使用率の取得方法"],
            round_finding_keys=[key("powershell", "usage")],
            seen_keys=set(),
            stagnation=1,
            round_num=2,
        )
        self.assertEqual(decision["action"], IMPLEMENT)
        self.assertEqual(decision["reason"], "missing_resolved")

    def test_new_finding_continues_and_resets_stagnation(self):
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用率の取得方法"],
            previous_missing=["メモリ使用率の取得方法"],
            round_finding_keys=[key("powershell", "B")],
            seen_keys={key("powershell", "A")},
            stagnation=2,
            round_num=3,
        )
        self.assertEqual(decision["action"], CONTINUE)
        self.assertEqual(decision["reason"], "new_information")
        self.assertEqual(decision["stagnation"], 0)
        self.assertTrue(decision["has_new_finding"])

    def test_new_finding_continues_even_if_missing_same(self):
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用率"],
            previous_missing=["使用率"],
            round_finding_keys=[key("powershell", "B")],
            seen_keys={key("powershell", "A")},
            stagnation=1,
            round_num=2,
        )
        self.assertEqual(decision["action"], CONTINUE)
        self.assertEqual(decision["reason"], "new_information")
        self.assertTrue(decision["missing_same"])

    def test_duplicate_and_same_missing_increments_stagnation(self):
        seen = {key("powershell", "A")}
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用率"],
            previous_missing=["使用率"],
            round_finding_keys=[key("powershell", "A")],
            seen_keys=seen,
            stagnation=0,
            round_num=2,
        )
        self.assertEqual(decision["action"], CONTINUE)
        self.assertEqual(decision["reason"], "no_progress")
        self.assertEqual(decision["stagnation"], 1)
        self.assertTrue(decision["duplicate_only"])

    def test_duplicate_but_missing_changed_is_progress(self):
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用中の割合"],
            previous_missing=["使用率"],
            round_finding_keys=[key("powershell", "A")],
            seen_keys={key("powershell", "A")},
            stagnation=2,
            round_num=3,
        )
        self.assertEqual(decision["action"], CONTINUE)
        self.assertEqual(decision["reason"], "new_information")
        self.assertEqual(decision["stagnation"], 0)
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用率"],
            previous_missing=["使用率"],
            round_finding_keys=[],
            seen_keys={key("powershell", "A")},
            stagnation=2,
            round_num=5,
        )
        self.assertEqual(decision["action"], STOP)
        self.assertEqual(decision["reason"], "stagnation")
        self.assertEqual(decision["stagnation"], 3)

    def test_max_rounds_stops_without_implement(self):
        decision = evaluate_research_progress(
            satisfies_request=False,
            missing=["使用率"],
            previous_missing=["別の質問"],
            round_finding_keys=[key("powershell", "new")],
            seen_keys=set(),
            stagnation=0,
            round_num=10,
            max_rounds=10,
        )
        self.assertEqual(decision["action"], STOP)
        self.assertEqual(decision["reason"], "max_research_rounds")

    def test_max_rounds_still_implements_when_complete(self):
        decision = evaluate_research_progress(
            satisfies_request=True,
            missing=[],
            previous_missing=["使用率"],
            round_finding_keys=[key("powershell", "usage")],
            seen_keys=set(),
            stagnation=0,
            round_num=10,
            max_rounds=10,
        )
        self.assertEqual(decision["action"], IMPLEMENT)

    def test_missing_normalization_ignores_order(self):
        self.assertEqual(
            normalize_missing(["b", "a", "a"]),
            normalize_missing(["a", "b"]),
        )


if __name__ == "__main__":
    unittest.main()
