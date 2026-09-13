"""KSS-1.1 Decision Evidence 観測の単体テスト。"""

import os
import unittest

from tools.ai.state.decision_evidence import (
    MISSING_FIELDS,
    capture_research_round_evidence,
    evidence_level_from_existing,
    kss11_obs_enabled,
    summarize_decision_evidence,
)


class Kss11DecisionEvidenceTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS11_OBS", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KSS11_OBS", None)
        self.assertFalse(kss11_obs_enabled())

    def test_evidence_level_uses_existing_labels_only(self):
        self.assertEqual(
            evidence_level_from_existing(verify_high=1),
            "high",
        )
        self.assertEqual(
            evidence_level_from_existing(web_kept=2),
            "medium",
        )
        self.assertEqual(
            evidence_level_from_existing(verify_low=1),
            "low",
        )
        self.assertEqual(evidence_level_from_existing(), "missing")

    def test_missing_not_invented_as_zero(self):
        bundle = capture_research_round_evidence(
            round_num=1,
            researched={
                "verified": {"results": []},
                "research": {},
                "web_hits": [],
                "candidates": [],
            },
            judgment={"satisfies_request": False, "missing": ["x"], "reason": "r"},
            gj_trigger={"needed": True, "would_skip": False},
            gj_result={},
            progress_decision={
                "action": "continue",
                "reason": "no_progress",
                "stagnation": 1,
                "has_new_finding": False,
                "missing_same": True,
                "duplicate_only": True,
            },
            max_rounds=10,
            max_stagnation=3,
        )
        self.assertTrue(bundle["enabled"])
        self.assertEqual(bundle["evidence"]["verify_confidence_numeric"], "missing")
        self.assertEqual(bundle["evidence"]["evidence_level"], "missing")
        judge_ev = next(
            e for e in bundle["decision_events"] if e["decision_type"] == "research_judge"
        )
        self.assertEqual(
            judge_ev["score_refs"]["llm_judge_confidence_numeric"], "missing"
        )

    def test_summary_includes_mapping_and_missing(self):
        bundle = capture_research_round_evidence(
            round_num=2,
            researched={
                "verified": {
                    "results": [
                        {
                            "confidence": "high",
                            "evidence": {"command": "powershell", "args": []},
                        }
                    ]
                },
                "research": {"usable_findings": [{"confidence": "high"}]},
                "web_hits": [{"title": "t"}],
            },
            judgment={"satisfies_request": True, "missing": []},
            gj_result={"live_skipped": False},
            progress_decision={
                "action": "implement",
                "reason": "findings_complete",
                "stagnation": 0,
                "has_new_finding": True,
                "missing_same": False,
                "duplicate_only": False,
            },
        )
        summary = summarize_decision_evidence([bundle])
        self.assertGreater(summary["decision_count"], 0)
        self.assertIn("deterministic_rule", summary["decision_source_distribution"])
        self.assertIn("verify_confidence_numeric", str(MISSING_FIELDS))
        self.assertEqual(summary["success_by_evidence_level"].get("high"), 1)


if __name__ == "__main__":
    unittest.main()
