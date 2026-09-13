import unittest

from research.llm_benchmarks.clarity_state_classify import (
    AMBIGUOUS_VALUE_MATERIALS,
    inspect_not_overwritten,
    inspect_state_in_research_messages,
    inspect_user_state,
    run_scripted_handoff,
)
from tools.ai.llm.adapter import build_state_query_messages
from tools.system.config import get_llm_profile


class ClarityStateHandoffTests(unittest.TestCase):
    def test_user_reply_becomes_state(self):
        result = run_scripted_handoff()
        self.assertEqual(result["next_step"], "research")
        report = inspect_user_state(result["state"])
        self.assertTrue(report["ok"], report["checks"])

    def test_research_and_judge_receive_state(self):
        state = run_scripted_handoff()["state"]
        report = inspect_state_in_research_messages(state)
        self.assertTrue(report["ok"], report["prompts"])
        self.assertTrue(report["prompts"]["research"]["state_before_materials"])
        self.assertTrue(report["prompts"]["judge"]["state_before_materials"])
        self.assertTrue(report["prompts"]["judge"]["sample_in_materials"])
        self.assertTrue(report["prompts"]["judge"]["meaning_not_only_from_materials"])

    def test_ambiguous_value_materials_do_not_name_memory(self):
        packed = str(AMBIGUOUS_VALUE_MATERIALS)
        self.assertIn("43.2", packed)
        self.assertNotIn("メモリ", packed)
        self.assertNotIn("使用率", packed)
        messages = build_state_query_messages(
            AMBIGUOUS_VALUE_MATERIALS,
            profile=get_llm_profile("qwen3_8b"),
        )
        user = messages[1]["content"]
        self.assertNotIn("TASK STATE", user)
        self.assertIn("43.2", user)

    def test_handoff_state_is_in_unit_question_prompt(self):
        state = run_scripted_handoff()["state"]
        messages = build_state_query_messages(
            AMBIGUOUS_VALUE_MATERIALS,
            profile=get_llm_profile("qwen3_8b"),
            state=state,
        )
        user = messages[1]["content"]
        self.assertLess(user.find("TASK STATE"), user.find("TASK MATERIALS"))
        self.assertIn("Windowsのメモリ使用率", user[: user.find("TASK MATERIALS")])
        materials = user[user.find("TASK MATERIALS") :]
        self.assertIn("43.2", materials)
        self.assertNotIn("メモリ使用率", materials)

    def test_meaning_scorer_accepts_state_keys(self):
        from research.llm_benchmarks.clarity_state_classify import (
            inspect_meaning_from_state,
        )

        held = inspect_meaning_from_state(
            {
                "answer": "%",
                "reason": "status.unit from the user's decision",
                "used_state_keys": ["status.meaning", "status.unit"],
            },
            {
                "recognized_memory_usage": False,
                "unit_percent": True,
                "reason_class": "state_based",
            },
        )
        self.assertTrue(held["memory"])
        self.assertTrue(held["unit"])
        self.assertTrue(held["state_based"])
        self.assertTrue(held["ok"])

    def test_judge_cannot_overwrite_user_state(self):
        state = run_scripted_handoff()["state"]
        report = inspect_not_overwritten(state)
        self.assertTrue(report["ok"], report["checks"])
        self.assertEqual(state.get_decision("status.unit")["source"], "user")
        self.assertEqual(state.get_decision("status.unit")["value"], "%")


if __name__ == "__main__":
    unittest.main()
