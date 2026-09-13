"""Memory Recall Policy 版切替（制御比較用）。"""

import os
import unittest

from tools.ai.state.memory_recall import (
    MODE_REPEATING,
    build_recall_bundle,
    memory_recall_policy_version,
)
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.task_state import TaskState


def _state_same_cmd_streak():
    events = [
        {
            "id": "evt_a",
            "type": "verify_fail",
            "action": {"command": "powershell", "args": ["-Command", "Get-X"]},
            "result": {"ok": False, "error": "empty"},
            "metadata": {"round": 1},
        },
        {
            "id": "evt_b",
            "type": "verify_fail",
            "action": {"command": "powershell", "args": ["-Command", "Get-X"]},
            "result": {"ok": False, "error": "empty"},
            "metadata": {"round": 2},
        },
    ]
    return TaskState(
        research_history=ResearchHistory.from_snapshot(events),
        open_questions=[
            {
                "id": "q1",
                "text": "t",
                "status": "open",
                "related_events": ["evt_a", "evt_b"],
            }
        ],
    )


class RecallVersionSwitchTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_MEMORY_RECALL_VERSION", None)
        os.environ.pop("AI_AGENT_MEMORY_RECALL", None)

    def test_default_is_5_1(self):
        os.environ.pop("AI_AGENT_MEMORY_RECALL_VERSION", None)
        self.assertEqual(memory_recall_policy_version(), "5.1")

    def test_version_5_selects_legacy(self):
        os.environ["AI_AGENT_MEMORY_RECALL"] = "1"
        os.environ["AI_AGENT_MEMORY_RECALL_VERSION"] = "5"
        self.assertEqual(memory_recall_policy_version(), "5")
        bundle = build_recall_bundle(_state_same_cmd_streak())
        self.assertEqual(bundle["mode"], MODE_REPEATING)
        self.assertEqual((bundle.get("policy_trace") or {}).get("phase"), "5")
        self.assertFalse(bundle.get("pivot_required"))

    def test_version_5_1_pivot(self):
        os.environ["AI_AGENT_MEMORY_RECALL"] = "1"
        os.environ["AI_AGENT_MEMORY_RECALL_VERSION"] = "5.1"
        bundle = build_recall_bundle(_state_same_cmd_streak())
        self.assertEqual(bundle["mode"], MODE_REPEATING)
        self.assertTrue(bundle.get("pivot_required"))
        self.assertIn("PIVOT REQUIRED", bundle.get("repeating_hint") or "")
        self.assertEqual((bundle.get("policy_trace") or {}).get("phase"), "5.1")


if __name__ == "__main__":
    unittest.main()
