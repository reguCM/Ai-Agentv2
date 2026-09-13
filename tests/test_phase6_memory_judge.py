"""Phase 6 Memory Judge 単体テスト（LLM はモック）。"""

import os
import unittest

from tools.ai.state.memory_judge import (
    apply_judgment_to_bundle,
    apply_memory_judge,
    memory_judge_enabled,
    normalize_memory_judgment,
)
from tools.ai.state.memory_recall import build_recall_bundle
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.task_state import TaskState


class MemoryJudgeTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AI_AGENT_MEMORY_JUDGE", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_MEMORY_JUDGE", None)
        self.assertFalse(memory_judge_enabled())

    def test_normalize_and_apply_selection(self):
        history = ResearchHistory.from_snapshot(
            [
                {
                    "id": "evt_1",
                    "type": "verify_fail",
                    "action": {"command": "powershell", "args": ["a"]},
                    "result": {"ok": False, "error": "not found"},
                    "metadata": {"round": 1},
                },
                {
                    "id": "evt_2",
                    "type": "verify_fail",
                    "action": {"command": "wmic", "args": ["cpu"]},
                    "result": {"ok": False, "error": "failed"},
                    "metadata": {"round": 2},
                },
            ]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "温度",
                    "status": "open",
                    "related_events": ["evt_1", "evt_2"],
                }
            ],
            research_history=history,
        )
        rule = build_recall_bundle(state)
        judgment = normalize_memory_judgment(
            {
                "mode": "related",
                "selected_event_ids": ["evt_2"],
                "omit_reason": "irrelevant",
                "hint": "try wmic path only",
            },
            fallback_bundle=rule,
        )
        out = apply_judgment_to_bundle(state, rule, judgment)
        self.assertEqual(out["mode"], "related")
        self.assertEqual(len(out["recalled_events"]), 1)
        self.assertEqual(out["recalled_events"][0]["id"], "evt_2")
        self.assertEqual(out["repeating_hint"], "try wmic path only")

    def test_apply_memory_judge_with_mock_chat(self):
        os.environ["AI_AGENT_MEMORY_JUDGE"] = "1"
        history = ResearchHistory.from_snapshot(
            [
                {
                    "id": "evt_1",
                    "type": "verify_fail",
                    "action": {"command": "powershell", "args": ["a"]},
                    "result": {"ok": False, "error": "not found"},
                    "metadata": {"round": 1},
                }
            ]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "温度",
                    "status": "open",
                    "related_events": ["evt_1"],
                }
            ],
            research_history=history,
        )
        rule = build_recall_bundle(state)

        def fake_chat(messages):
            return (
                '{"mode":"fresh","selected_event_ids":[],'
                '"omit_reason":"new_problem","hint":""}'
            )

        out = apply_memory_judge(state, rule, chat_fn=fake_chat)
        self.assertEqual(out["mode"], "fresh")
        self.assertEqual(out["recalled_events"], [])
        self.assertEqual(out["policy_trace"].get("memory_judge"), "applied")

    def test_fallback_on_bad_json(self):
        os.environ["AI_AGENT_MEMORY_JUDGE"] = "1"
        state = TaskState(task="t")
        rule = build_recall_bundle(state)

        def bad_chat(messages):
            return "not json"

        out = apply_memory_judge(state, rule, chat_fn=bad_chat)
        self.assertTrue(
            str(out["policy_trace"].get("memory_judge", "")).startswith("fallback")
        )


if __name__ == "__main__":
    unittest.main()
