"""Phase 5 / 5.1 Memory Recall 単体テスト。"""

import os
import unittest

from tools.ai.state.memory_recall import (
    MODE_FRESH,
    MODE_RELATED,
    MODE_REPEATING,
    assess_information_gain,
    build_recall_bundle,
    command_family,
    decide_recall_mode,
    memory_recall_enabled,
    score_event,
)
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.retrieve import classify_error_class
from tools.ai.state.task_state import TaskState


def _fail_event(eid, command, args, error, round_num=1):
    return {
        "id": eid,
        "type": "verify_fail",
        "action": {"command": command, "args": args},
        "result": {"ok": False, "error": error, "stderr": error},
        "metadata": {"round": round_num},
    }


def _ok_event(eid, command, args, round_num=1):
    return {
        "id": eid,
        "type": "verify_ok",
        "action": {"command": command, "args": args},
        "result": {"ok": True, "sample": ["42"]},
        "metadata": {"round": round_num},
    }


class MemoryRecallTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("AI_AGENT_MEMORY_RECALL", None)

    def test_memory_recall_enabled_by_default(self):
        os.environ.pop("AI_AGENT_MEMORY_RECALL", None)
        self.assertTrue(memory_recall_enabled())
        os.environ["AI_AGENT_MEMORY_RECALL"] = "0"
        self.assertFalse(memory_recall_enabled())

    def test_classify_error_class(self):
        self.assertEqual(
            classify_error_class("Property 'Foo' does not exist"),
            "property_not_found",
        )
        self.assertEqual(classify_error_class(""), "empty_sample")

    def test_command_family_extracts_token(self):
        fam = command_family(
            {
                "command": "powershell",
                "args": ["-Command", "Get-WmiObject -Class Win32_Processor"],
            }
        )
        self.assertEqual(fam[0], "powershell")
        self.assertIn("win32_processor", fam[1])

    def test_fresh_mode_when_few_failures(self):
        history = ResearchHistory.from_snapshot(
            [_fail_event("evt_1", "powershell", ["-Command", "x"], "not found", 1)]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "CPU温度",
                    "status": "open",
                    "related_events": ["evt_1"],
                }
            ],
            research_history=history,
        )
        mode, _ = decide_recall_mode(state)
        self.assertEqual(mode, MODE_FRESH)
        bundle = build_recall_bundle(state, current_round=1)
        self.assertEqual(bundle["mode"], MODE_FRESH)
        self.assertLessEqual(len(bundle["recalled_events"]), 1)
        self.assertFalse(bundle.get("pivot_required"))

    def test_repeating_on_error_class_across_different_commands(self):
        """command が変わっても同 error_class + 情報非増加 → repeating + pivot。"""
        events = [
            _fail_event(
                "evt_1",
                "powershell",
                ["-Command", "Get-WmiObject Win32_TemperatureProbe"],
                "empty output",
                1,
            ),
            _fail_event(
                "evt_2",
                "powershell",
                ["-Command", "Get-CimInstance Win32_TemperatureProbe"],
                "blank result",
                2,
            ),
        ]
        history = ResearchHistory.from_snapshot(events)
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
        mode, reason = decide_recall_mode(state)
        self.assertEqual(mode, MODE_REPEATING)
        self.assertIn("no_information_gain", reason)
        bundle = build_recall_bundle(state, current_round=3)
        self.assertEqual(bundle["mode"], MODE_REPEATING)
        self.assertTrue(bundle["pivot_required"])
        self.assertIn("PIVOT REQUIRED", bundle["repeating_hint"])
        # 増量しない
        self.assertLessEqual(len(bundle["prior_failures"]), 2)
        self.assertEqual(bundle.get("stuck_error_class"), "empty_sample")

    def test_exact_command_repeat_alone_is_not_primary_without_class_stuck(self):
        """異なる error_class なら exact 同一でも related（banned に委譲）。"""
        events = [
            _fail_event("evt_1", "wmic", ["cpu"], "Property Temp does not exist", 1),
            _fail_event("evt_2", "powershell", ["x"], "timed out waiting", 2),
        ]
        history = ResearchHistory.from_snapshot(events)
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
        mode, _ = decide_recall_mode(state)
        self.assertEqual(mode, MODE_RELATED)

    def test_information_gain_blocks_repeating(self):
        events = [
            _fail_event("evt_1", "powershell", ["a"], "empty", 1),
            _ok_event("evt_ok", "powershell", ["b"], 2),
            _fail_event("evt_2", "powershell", ["c"], "empty again", 3),
        ]
        history = ResearchHistory.from_snapshot(events)
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
            selected_findings=[{"summary": "got a value", "finding_ref": "evt_ok"}],
        )
        info = assess_information_gain(state)
        self.assertTrue(info["has_gain"] or not info["no_gain"])
        mode, _ = decide_recall_mode(state)
        self.assertNotEqual(mode, MODE_REPEATING)

    def test_score_prefers_open_question_and_error_class(self):
        history = ResearchHistory.from_snapshot(
            [_fail_event("evt_1", "powershell", ["a"], "not found", 1)]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "q",
                    "status": "open",
                    "related_events": ["evt_1"],
                }
            ],
            research_history=history,
        )
        score, reasons = score_event(
            state,
            history.events[0],
            current_round=1,
            focus_error_class="property_not_found",
        )
        self.assertGreaterEqual(score, 4)
        self.assertIn("open_question_link", reasons)

    def test_thin_handoff_when_recall_enabled(self):
        os.environ.pop("AI_AGENT_MEMORY_RECALL", None)
        from tools.ai.tool_builder.research_judge import prepare_followup_research

        research = {
            "unresolved": [
                {
                    "question": "q",
                    "finding": "f",
                    "evidence": {"command": "powershell", "args": ["x"], "error": "e"},
                }
            ]
        }
        handoff = prepare_followup_research(
            ["gap"], research, reason="long reason " * 20
        )
        self.assertTrue(handoff.get("memory_recall"))
        self.assertEqual(handoff.get("prior_failures"), [])
        self.assertEqual(handoff.get("judge_reason"), "")
        self.assertEqual(handoff["followup_questions"], ["gap"])


if __name__ == "__main__":
    unittest.main()
