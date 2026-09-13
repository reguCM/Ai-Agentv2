"""KSS-1 Decision Confidence 観測の単体テスト（行動変更なし）。"""

import os
import unittest

from tools.ai.state.decision_confidence import (
    OUTCOME_SUCCESS,
    OUTCOME_USEFUL_FAILURE,
    OUTCOME_ZERO_INFO,
    classify_outcome,
    detect_high_confidence_stuck,
    extract_payload_observation,
    kss1_obs_enabled,
    link_decisions_to_results,
    observe_candidate_decision_payload,
    strip_observation_fields,
    summarize_calibration,
)


class Kss1DecisionConfidenceTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS1_OBS", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KSS1_OBS", None)
        self.assertFalse(kss1_obs_enabled())

    def test_extract_and_strip_does_not_keep_obs_on_candidates(self):
        payload = {
            "candidates": [
                {
                    "command": "powershell",
                    "args": ["x"],
                    "question": "q",
                    "observation": {
                        "action_confidence": 0.9,
                        "preferred_source": "external_research",
                    },
                }
            ],
            "observation": {"problem_confidence": 0.7},
        }
        extracted = extract_payload_observation(payload)
        self.assertEqual(extracted["per_candidate"][0]["action_confidence"], 0.9)
        self.assertEqual(extracted["round_observation"]["problem_confidence"], 0.7)
        cleaned = strip_observation_fields(payload["candidates"])
        self.assertNotIn("observation", cleaned[0])
        self.assertEqual(cleaned[0]["command"], "powershell")

    def test_missing_confidence_is_none_not_zero(self):
        payload = {"candidates": [{"command": "wmic", "args": []}]}
        obs = observe_candidate_decision_payload(payload, payload["candidates"])
        dec = obs["decisions"][0]
        self.assertIsNone(dec["action_confidence"])
        self.assertFalse(dec["observation_present"])

    def test_classify_zero_info_uses_no_gain(self):
        out = classify_outcome(
            actual_success=False,
            coverage_before={"no_gain": True},
            coverage_after={"no_gain": True},
        )
        self.assertEqual(out["outcome_class"], OUTCOME_ZERO_INFO)
        self.assertTrue(out["actual_no_gain"])

    def test_classify_useful_failure(self):
        out = classify_outcome(
            actual_success=False,
            coverage_before={"no_gain": True, "has_usable_in_state": False},
            coverage_after={"no_gain": False, "has_usable_in_state": False},
        )
        self.assertEqual(out["outcome_class"], OUTCOME_USEFUL_FAILURE)

    def test_link_and_high_confidence_zero_gain(self):
        decisions = [
            {
                "decision_id": "decision_a",
                "action": {"command": "powershell", "args": ["a"]},
                "action_confidence": 0.91,
                "observation_present": True,
            }
        ]
        verified = [
            {
                "confidence": "low",
                "evidence": {
                    "command": "powershell",
                    "args": ["a"],
                    "error": "empty",
                },
            }
        ]
        linked = link_decisions_to_results(
            decisions,
            verified,
            coverage_before={"no_gain": True, "stuck_error_class": "empty_sample"},
            coverage_after={"no_gain": True, "stuck_error_class": "empty_sample"},
        )
        self.assertTrue(linked[0]["result_linked"])
        self.assertTrue(linked[0]["high_confidence_zero_gain"])
        self.assertEqual(linked[0]["outcome_class"], OUTCOME_ZERO_INFO)

    def test_stuck_detector(self):
        rounds = [
            {
                "round": 2,
                "decisions": [
                    {
                        "decision_id": "d1",
                        "action_confidence": 0.81,
                        "actual_no_gain": True,
                        "error_class": "empty_sample",
                        "high_confidence_zero_gain": True,
                    }
                ],
            },
            {
                "round": 3,
                "decisions": [
                    {
                        "decision_id": "d2",
                        "action_confidence": 0.87,
                        "actual_no_gain": True,
                        "error_class": "empty_sample",
                        "high_confidence_zero_gain": True,
                    }
                ],
            },
        ]
        events = detect_high_confidence_stuck(rounds)
        self.assertTrue(events)
        self.assertEqual(events[-1]["stuck_error_class"], "empty_sample")
        self.assertEqual(events[-1]["confidence_trend"], "increasing")

    def test_summary_buckets(self):
        linked = [
            {
                "action_confidence": 0.9,
                "outcome_class": OUTCOME_ZERO_INFO,
                "actual_information_gain": False,
                "actual_no_gain": True,
                "preferred_source": "external_research",
                "actual_success": False,
                "error_class": "empty_sample",
                "command_family": ["powershell", "x"],
            },
            {
                "action_confidence": 0.3,
                "outcome_class": OUTCOME_SUCCESS,
                "actual_information_gain": True,
                "actual_no_gain": False,
                "preferred_source": "state",
                "actual_success": True,
            },
            {
                "action_confidence": None,
                "outcome_class": OUTCOME_USEFUL_FAILURE,
                "observation_present": False,
            },
        ]
        summary = summarize_calibration(linked)
        self.assertEqual(summary["decisions_with_observation"], 2)
        self.assertIsNotNone(summary["high_confidence_zero_gain_rate"])
        self.assertEqual(summary["confidence_buckets"]["missing"]["observation_missing"], 1)


if __name__ == "__main__":
    unittest.main()
