import unittest

from tools.ai.tool_builder.web import (
    JUDGE_REASON_MAX_CHARS,
    compact_judge_reason_for_candidate,
    web_research,
)


class WebCandidateJudgeReasonTests(unittest.TestCase):
    def test_short_reason_unchanged(self):
        reason = "a" * JUDGE_REASON_MAX_CHARS
        self.assertEqual(compact_judge_reason_for_candidate(reason), reason)

    def test_long_reason_truncated(self):
        reason = "b" * (JUDGE_REASON_MAX_CHARS + 60)
        compacted = compact_judge_reason_for_candidate(reason)
        self.assertEqual(len(compacted), JUDGE_REASON_MAX_CHARS + 1)
        self.assertTrue(compacted.endswith("…"))
        self.assertEqual(compacted[:JUDGE_REASON_MAX_CHARS], reason[:JUDGE_REASON_MAX_CHARS])

    def test_empty_reason(self):
        self.assertEqual(compact_judge_reason_for_candidate(""), "")

    def test_none_reason(self):
        self.assertEqual(compact_judge_reason_for_candidate(None), "")

    def test_web_research_materials_use_compacted_reason(self):
        long_reason = "c" * 300
        materials = web_research(
            judge_reason=long_reason,
            inventory={"available_commands": ["powershell"]},
        )
        self.assertEqual(materials["judge_reason"], compact_judge_reason_for_candidate(long_reason))


if __name__ == "__main__":
    unittest.main()
