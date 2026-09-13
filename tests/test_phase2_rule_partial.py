import copy
import json
import unittest

from tools.ai.state.retrieve import (
    event_preview,
    get_event,
    parse_event_ref,
    resolve_event_refs,
    retrieve_by_command,
    retrieve_events_for_question,
    retrieve_failures_for_open_questions,
)
from tools.ai.state.rule_partial import apply_rule_partial, decide_escalation
from tools.ai.state.state_sync import sync_research_into_state
from tools.ai.state.task_state import TaskState


LONG_ERROR = "Select-Object : プロパティ Temperature が見つかりません。" + ("x" * 200)

FAILURE = {
    "kind": "output",
    "question": "CPU温度の取得方法が未確認",
    "finding": "実環境で確認できなかった。",
    "evidence": {
        "command": "powershell",
        "args": ["-Command", "Get-WmiObject Win32_Processor | Select Temperature"],
        "error": LONG_ERROR,
        "stderr": LONG_ERROR,
        "sample": [],
        "returncode": 1,
    },
    "confidence": "low",
    "source": "web",
}

USABLE = {
    "kind": "output",
    "question": "memory usage",
    "finding": "PercentCommittedBytesInUse で取得できる",
    "evidence": {
        "command": "powershell",
        "args": ["-Command", "Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory"],
        "sample": ["42.5"],
        "returncode": 0,
    },
    "confidence": "high",
    "source": "web",
}


class RetrieverTests(unittest.TestCase):
    def test_parse_and_resolve_event_ref(self):
        state = TaskState(task="t")
        result = apply_rule_partial(
            state, {"unresolved": [FAILURE]}, round_num=1
        )
        event_id = result["event_ids"][0]
        self.assertEqual(parse_event_ref(f"event:{event_id}"), event_id)
        unresolved = state.unresolved
        self.assertTrue(unresolved)
        resolved = resolve_event_refs(state.research_history, unresolved)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["id"], event_id)
        self.assertEqual(resolved[0]["result"]["error"], LONG_ERROR)

    def test_retrieve_events_for_question(self):
        state = TaskState(task="t")
        apply_rule_partial(state, {"unresolved": [FAILURE]}, round_num=1)
        qid = state.open_questions[0]["id"]
        events = retrieve_events_for_question(state, qid, limit=3)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "verify_fail")
        failures = retrieve_failures_for_open_questions(state)
        self.assertEqual(len(failures), 1)

    def test_retrieve_by_command(self):
        state = TaskState(task="t")
        apply_rule_partial(state, {"unresolved": [FAILURE]}, round_num=1)
        matched = retrieve_by_command(
            state.research_history,
            "powershell",
            ["-Command", "Get-WmiObject Win32_Processor | Select Temperature"],
        )
        self.assertEqual(len(matched), 1)

    def test_event_preview_truncates_error(self):
        state = TaskState(task="t")
        result = apply_rule_partial(
            state, {"unresolved": [FAILURE]}, round_num=1
        )
        event = get_event(state.research_history, result["event_ids"][0])
        preview = event_preview(event, error_chars=40)
        self.assertLessEqual(len(preview["error_preview"]), 41)
        self.assertNotEqual(preview["error_preview"], LONG_ERROR)


class RulePartialTests(unittest.TestCase):
    def test_verify_fail_adds_open_question_and_ban(self):
        state = TaskState(task="t")
        research = {"unresolved": [copy.deepcopy(FAILURE)]}
        original = copy.deepcopy(research)
        result = apply_rule_partial(state, research, round_num=2)
        self.assertEqual(research, original)
        self.assertEqual(len(state.open_questions), 1)
        self.assertEqual(len(state.banned_actions), 1)
        self.assertEqual(state.banned_actions[0]["command"], "powershell")
        ops = [p.get("op") for p in result["applied"]]
        self.assertIn("add_open_question", ops)
        self.assertIn("ban_action", ops)
        self.assertTrue(result["findings_recorded"])
        self.assertTrue(result["needs_global_judge"])
        self.assertEqual(
            (result["escalation"] or {}).get("reason"),
            "verify_fail_open_questions_updated",
        )
        self.assertTrue((result["escalation"] or {}).get("routine"))
        joined = json.dumps(state.snapshot(), ensure_ascii=False)
        self.assertNotIn(LONG_ERROR[:50], joined)
        self.assertNotIn("banned_actions", joined)

    def test_usable_adds_selected_and_escalates_goal_check(self):
        state = TaskState(task="t")
        result = apply_rule_partial(
            state, {"usable_findings": [USABLE]}, round_num=1
        )
        self.assertEqual(len(state.selected_findings), 1)
        self.assertTrue(state.selected_findings[0]["finding_ref"].startswith("evt_"))
        self.assertEqual(
            (result["escalation"] or {}).get("reason"),
            "usable_needs_goal_check",
        )
        self.assertFalse((result["escalation"] or {}).get("routine"))

    def test_ambiguous_reference_escalates_via_partial_unavailable(self):
        state = TaskState(task="t")
        ref = {
            "kind": "output",
            "question": "maybe",
            "finding": "unclear",
            "confidence": "medium",
            "evidence": {"command": "wmic", "args": [], "sample": []},
        }
        escalation = decide_escalation(
            {"reference_findings": [ref]},
            state=state,
            event_ids=[],
            applied_patches=[],
        )
        self.assertEqual(escalation["level"], "global_judge")
        self.assertEqual(escalation["via"], "partial_llm_unavailable")
        self.assertTrue(escalation["needs_partial_llm"])

    def test_sync_skips_duplicate_findings_after_rule_partial(self):
        state = TaskState(task="t")
        round_research = {"unresolved": [FAILURE], "usable_findings": []}
        apply_rule_partial(state, round_research, round_num=1)
        before = len(state.research_history.events)
        sync_research_into_state(
            state,
            research=round_research,
            round_num=1,
            judgment={
                "satisfies_request": False,
                "missing": ["CPU温度の取得方法が未確認"],
                "reason": "still missing",
            },
            previous_missing=None,
            round_research=round_research,
            skip_round_findings=True,
        )
        after = len(state.research_history.events)
        # judge event only
        self.assertEqual(after, before + 1)
        self.assertEqual(
            sum(1 for e in state.research_history.events if e["type"] == "verify_fail"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
