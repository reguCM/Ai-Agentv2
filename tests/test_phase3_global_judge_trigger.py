import unittest

from tools.ai.state.global_judge_trigger import (
    TRIGGER_FINAL_ROUND,
    TRIGGER_FIRST_ROUND,
    TRIGGER_ROUTINE_VERIFY_FAIL,
    TRIGGER_USABLE_NEEDS_GOAL,
    build_shadow_judgment,
    compare_shadow_vs_actual,
    evaluate_global_judge_trigger,
    execute_global_judge_round,
    init_shadow_summary,
    record_shadow_round,
    should_audit_skip_round,
)
from tools.ai.state.task_state import TaskState


class GlobalJudgeTriggerTests(unittest.TestCase):
    def test_routine_verify_fail_would_skip(self):
        escalation = {
            "reason": "verify_fail_open_questions_updated",
            "routine": True,
            "needs_partial_llm": False,
        }
        result = evaluate_global_judge_trigger(
            escalation,
            round_num=3,
            round_research={"unresolved": [{}], "usable_findings": []},
            stagnation=0,
            max_rounds=10,
            max_stagnation=3,
        )
        self.assertFalse(result["needed"])
        self.assertTrue(result["would_skip"])
        self.assertIn(TRIGGER_ROUTINE_VERIFY_FAIL, result["skip_triggers"])
        self.assertEqual(result["llm_calls_saved_if_skip"], 1)

    def test_first_round_never_skip(self):
        escalation = {
            "reason": "verify_fail_open_questions_updated",
            "routine": True,
        }
        result = evaluate_global_judge_trigger(
            escalation,
            round_num=1,
            round_research={"unresolved": [{}]},
            stagnation=0,
        )
        self.assertTrue(result["needed"])
        self.assertFalse(result["would_skip"])
        self.assertIn(TRIGGER_FIRST_ROUND, result["triggers"])

    def test_usable_needs_global(self):
        escalation = {
            "reason": "usable_needs_goal_check",
            "routine": False,
        }
        result = evaluate_global_judge_trigger(
            escalation,
            round_num=4,
            round_research={"usable_findings": [{"confidence": "high"}]},
            stagnation=0,
        )
        self.assertTrue(result["needed"])
        self.assertFalse(result["would_skip"])
        self.assertIn(TRIGGER_USABLE_NEEDS_GOAL, result["triggers"])

    def test_final_round_never_skip(self):
        escalation = {
            "reason": "verify_fail_open_questions_updated",
            "routine": True,
        }
        result = evaluate_global_judge_trigger(
            escalation,
            round_num=10,
            round_research={"unresolved": [{}]},
            stagnation=0,
            max_rounds=10,
        )
        self.assertTrue(result["needed"])
        self.assertFalse(result["would_skip"])
        self.assertIn(TRIGGER_FINAL_ROUND, result["triggers"])

    def test_partial_llm_unavailable_never_skip(self):
        escalation = {
            "reason": "ambiguous_reference_only",
            "needs_partial_llm": True,
            "routine": False,
        }
        result = evaluate_global_judge_trigger(
            escalation,
            round_num=5,
            round_research={"reference_findings": [{}]},
            stagnation=0,
        )
        self.assertTrue(result["needed"])
        self.assertFalse(result["would_skip"])

    def test_shadow_judgment_and_compare(self):
        state = TaskState(task="t")
        state.open_questions = [
            {"id": "q1", "text": "CPU温度", "status": "open", "related_events": []}
        ]
        shadow = build_shadow_judgment(state, {"reason": "verify_fail_open_questions_updated"})
        actual = {
            "satisfies_request": False,
            "missing": ["CPU温度"],
            "reason": "not yet",
        }
        cmp = compare_shadow_vs_actual(shadow, actual)
        self.assertTrue(cmp["satisfies_request_match"])
        self.assertTrue(cmp["missing_match"])
        self.assertFalse(cmp["critical_miss"])

    def test_critical_miss_detected(self):
        shadow = {"satisfies_request": False, "missing": ["a"]}
        actual = {"satisfies_request": True, "missing": []}
        cmp = compare_shadow_vs_actual(shadow, actual)
        self.assertTrue(cmp["critical_miss"])

    def test_shadow_summary_aggregation(self):
        summary = init_shadow_summary()
        summary = record_shadow_round(
            summary,
            {
                "round": 2,
                "would_skip": True,
                "llm_calls_saved_if_skip": 1,
                "llm_called": True,
                "live_skipped": False,
                "quality_compare": {
                    "critical_miss": False,
                    "false_continue": False,
                    "satisfies_request_match": True,
                    "missing_match": False,
                },
            },
        )
        self.assertEqual(summary["rounds_total"], 1)
        self.assertEqual(summary["would_skip_count"], 1)
        self.assertEqual(summary["judge_calls_actual"], 1)
        self.assertEqual(summary["quality"]["satisfies_match_count"], 1)

    def test_decision_divergence_in_compare(self):
        shadow = {"satisfies_request": False, "missing": ["a"]}
        actual = {"satisfies_request": True, "missing": []}
        cmp = compare_shadow_vs_actual(
            shadow,
            actual,
            progress_context={
                "previous_missing": ["a"],
                "round_finding_keys": [],
                "seen_keys": set(),
                "stagnation": 0,
                "round_num": 2,
                "max_rounds": 10,
                "max_stagnation": 3,
            },
        )
        self.assertTrue(cmp["critical_miss"])
        self.assertTrue(cmp["decision_divergence"])
        self.assertEqual(cmp["shadow_progress_action"], "continue")
        self.assertEqual(cmp["actual_progress_action"], "implement")

    def test_finalize_observation(self):
        from tools.ai.state.global_judge_trigger import finalize_observation

        summary = init_shadow_summary()
        summary = record_shadow_round(
            summary,
            {
                "round": 2,
                "would_skip": True,
                "llm_calls_saved_if_skip": 1,
                "llm_called": False,
                "live_skipped": True,
            },
        )
        summary = record_shadow_round(
            summary,
            {
                "round": 3,
                "would_skip": False,
                "llm_called": True,
                "live_skipped": False,
            },
        )
        summary = finalize_observation(summary, rounds=5, baseline_rounds=3)
        self.assertEqual(summary["observation"]["extra_rounds"], 2)
        self.assertEqual(summary["observation"]["judge_reduction_rate"], 0.5)

    def test_live_skip_default_on(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP", None)
            from tools.ai.state.global_judge_trigger import is_live_skip_enabled

            self.assertTrue(is_live_skip_enabled())
        with mock.patch.dict(os.environ, {"AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "0"}):
            from tools.ai.state.global_judge_trigger import is_live_skip_enabled

            self.assertFalse(is_live_skip_enabled())

    def test_live_skip_skips_llm(self):
        import os
        from unittest import mock

        escalation = {
            "reason": "verify_fail_open_questions_updated",
            "routine": True,
        }
        trigger = evaluate_global_judge_trigger(
            escalation,
            round_num=3,
            round_research={"unresolved": [{}]},
            stagnation=0,
        )
        state = TaskState(task="t")
        state.open_questions = [
            {"id": "q1", "text": "CPU温度", "status": "open", "related_events": []}
        ]
        calls = {"n": 0}

        def fake_judge():
            calls["n"] += 1
            return {
                "payload": {"satisfies_request": True},
                "error": None,
                "text": "x",
                "detail": None,
                "judgment": {"satisfies_request": True, "missing": []},
                "judge_held": {},
            }

        with mock.patch.dict(os.environ, {"AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1"}):
            result = execute_global_judge_round(
                gj_trigger=trigger,
                state=state,
                escalation=escalation,
                round_num=3,
                run_llm_judge=fake_judge,
            )
        self.assertTrue(result["live_skipped"])
        self.assertFalse(result["llm_called"])
        self.assertEqual(calls["n"], 0)
        self.assertTrue(result["judgment"].get("live_skip"))

    def test_live_skip_audit_calls_llm(self):
        import os
        from unittest import mock

        escalation = {
            "reason": "verify_fail_open_questions_updated",
            "routine": True,
        }
        trigger = evaluate_global_judge_trigger(
            escalation,
            round_num=20,
            round_research={"unresolved": [{}]},
            stagnation=0,
            max_rounds=30,
        )
        state = TaskState(task="t")
        calls = {"n": 0}

        def fake_judge():
            calls["n"] += 1
            return {
                "payload": {},
                "error": None,
                "text": "",
                "detail": None,
                "judgment": {"satisfies_request": False, "missing": ["a"]},
                "judge_held": {},
            }

        with mock.patch.dict(
            os.environ,
            {
                "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1",
                "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE": "2",
            },
        ):
            result = execute_global_judge_round(
                gj_trigger=trigger,
                state=state,
                escalation=escalation,
                round_num=20,
                run_llm_judge=fake_judge,
                skip_event_index=2,
            )
        self.assertTrue(result["audit_only"])
        self.assertTrue(result["llm_called"])
        self.assertFalse(result["live_skipped"])
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
