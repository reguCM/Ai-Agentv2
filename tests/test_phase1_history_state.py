import copy
import json
import unittest

from tools.ai.state.open_questions import compact_unresolved_for_state
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.state_patch import apply_state_patches
from tools.ai.state.state_sync import sync_research_into_state
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.research_result import compact_prior_failures, rejected_command_list
from tools.ai.tool_builder.web import compact_prior_failures_for_candidate


LONG_ERROR = (
    'Select-Object : プロパティ "Temperature" が見つかりません。\n'
    + ("x" * 400)
)

FAILURE_FINDING = {
    "kind": "output",
    "question": "CPU温度の具体的な取得方法が確認できていない",
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


class ResearchHistoryTests(unittest.TestCase):
    def test_append_only(self):
        history = ResearchHistory()
        first = history.append("verify_fail", action={"command": "wmic"})
        second = history.append("judge", result={"satisfies_request": False})
        self.assertEqual(len(history.events), 2)
        self.assertEqual(history.events[0]["id"], first)
        self.assertEqual(history.events[1]["id"], second)

    def test_record_finding_stores_full_error(self):
        history = ResearchHistory()
        event_id = history.record_finding(FAILURE_FINDING, event_type="verify_fail", round_num=2)
        event = history.events[0]
        self.assertEqual(event["id"], event_id)
        self.assertEqual(event["result"]["error"], LONG_ERROR)
        self.assertEqual(event["action"]["command"], "powershell")

    def test_snapshot_is_copy(self):
        history = ResearchHistory()
        history.append("judge")
        snap = history.snapshot()
        snap.clear()
        self.assertEqual(len(history.events), 1)


class OpenQuestionsTests(unittest.TestCase):
    def test_add_and_resolve(self):
        state = TaskState(task="t")
        history = state.research_history
        from tools.ai.state.open_questions import ensure_open_question, resolve_open_question

        qid = ensure_open_question(state, "CPU温度の取得方法")
        self.assertEqual(len(state.open_questions), 1)
        self.assertTrue(resolve_open_question(state, qid, history=history, reason="test"))
        self.assertEqual(len(state.open_questions), 0)

    def test_compact_unresolved_has_no_long_stderr(self):
        state = TaskState(task="t")
        sync_research_into_state(
            state,
            research={"unresolved": [FAILURE_FINDING]},
            round_num=1,
            round_research={"unresolved": [FAILURE_FINDING]},
        )
        self.assertLess(len(json.dumps(state.unresolved, ensure_ascii=False)), 300)
        joined = json.dumps(state.unresolved, ensure_ascii=False)
        self.assertNotIn(LONG_ERROR[:80], joined)

    def test_resolve_records_history(self):
        state = TaskState(task="t")
        history = state.research_history
        sync_research_into_state(
            state,
            research={"unresolved": []},
            round_num=1,
            judgment={
                "satisfies_request": False,
                "missing": ["CPU温度の取得方法"],
                "reason": "not yet",
            },
            previous_missing=["CPU温度の取得方法", "used memory is still unconfirmed"],
            round_research={"unresolved": []},
        )
        sync_research_into_state(
            state,
            research={"unresolved": []},
            round_num=2,
            judgment={
                "satisfies_request": False,
                "missing": ["used memory is still unconfirmed"],
                "reason": "still missing",
            },
            previous_missing=["CPU温度の取得方法", "used memory is still unconfirmed"],
            round_research={"unresolved": []},
        )
        resolved = [
            e for e in history.events if e["type"] == "question_resolved"
        ]
        self.assertEqual(len(resolved), 1)


class StateSyncTests(unittest.TestCase):
    def test_sync_keeps_research_dict_unmodified(self):
        research = {"unresolved": [copy.deepcopy(FAILURE_FINDING)]}
        original = copy.deepcopy(research)
        state = TaskState(task="t")
        sync_research_into_state(
            state,
            research=research,
            round_num=1,
            round_research=research,
        )
        self.assertEqual(research, original)

    def test_state_patch_resolve(self):
        state = TaskState(task="t")
        history = state.research_history
        from tools.ai.state.open_questions import ensure_open_question

        qid = ensure_open_question(state, "disk usage method")
        applied = apply_state_patches(
            state,
            [{"op": "resolve_question", "question_id": qid, "reason": "manual"}],
            history=history,
        )
        self.assertEqual(len(applied), 1)
        self.assertEqual(
            [q for q in state.open_questions if q["status"] == "open"],
            [],
        )


class CompatibilityTests(unittest.TestCase):
    def test_prior_failures_and_rejected_commands_unchanged(self):
        research = {
            "unresolved": [FAILURE_FINDING],
            "insufficient_findings": [],
        }
        prior = compact_prior_failures(research)
        rejected = rejected_command_list(research)
        compacted = compact_prior_failures_for_candidate(prior, rejected)
        self.assertEqual(len(prior), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIn("command", prior[0])
        self.assertTrue(compacted)

    def test_legacy_set_unresolved_still_works(self):
        state = TaskState(task="t")
        state.set_unresolved([FAILURE_FINDING])
        self.assertEqual(len(state.open_questions), 1)
        self.assertEqual(len(state.research_history.events), 1)
        self.assertNotIn(LONG_ERROR, json.dumps(state.snapshot(), ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
