"""KSS-1.2 web↔decision link 観測の単体テスト。"""

import os
import unittest

from tools.ai.state.web_decision_link import (
    annotate_hits_with_scores,
    kss12_obs_enabled,
    link_candidates_to_hits,
    maybe_link_web_to_decisions,
)
from research.llm_benchmarks.kss12_calibration import (
    audit_code_linkage,
    calibrate_from_rounds,
)


class Kss12WebDecisionLinkTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS12_OBS", None)
        os.environ.pop("AI_AGENT_KSS11_OBS", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KSS12_OBS", None)
        os.environ.pop("AI_AGENT_KSS11_OBS", None)
        self.assertFalse(kss12_obs_enabled())

    def test_inherits_kss11_flag(self):
        os.environ["AI_AGENT_KSS11_OBS"] = "1"
        self.assertTrue(kss12_obs_enabled())

    def test_annotate_adds_score_without_mutating_behavior(self):
        hits = [
            {
                "title": "Get Win32_OperatingSystem FreePhysicalMemory",
                "snippet": "WMI memory",
                "url": "https://learn.microsoft.com/os",
                "backend": "learn.microsoft",
            }
        ]
        scored = annotate_hits_with_scores(hits)
        self.assertIn("score", scored[0])
        self.assertNotIn("score", hits[0])

    def test_link_by_token_overlap(self):
        hits = [
            {
                "title": "Win32_OperatingSystem FreePhysicalMemory",
                "snippet": "TotalVisibleMemorySize",
                "url": "https://example/a",
            },
            {
                "title": "unrelated disk volume",
                "snippet": "Get-Volume",
                "url": "https://example/b",
            },
        ]
        cands = [
            {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-WmiObject Win32_OperatingSystem | Select FreePhysicalMemory",
                ],
            }
        ]
        linked = link_candidates_to_hits(cands, hits)
        self.assertTrue(linked["candidate_hit_links"][0]["linked"])
        self.assertEqual(linked["candidate_hit_links"][0]["best_hit_index"], 0)
        self.assertGreater(linked["link_coverage"], 0)

    def test_maybe_disabled_returns_flag(self):
        os.environ["AI_AGENT_KSS12_OBS"] = "0"
        out = maybe_link_web_to_decisions([], [])
        self.assertFalse(out.get("enabled"))

    def test_calibration_uses_decision_events(self):
        rounds = [
            {
                "round": 1,
                "verified_runs": [
                    {"ok": True, "confidence": "high", "command": "powershell", "args": []}
                ],
                "web_hits": [
                    {
                        "title": "powershell memory",
                        "snippet": "FreePhysicalMemory",
                        "url": "https://x",
                    }
                ],
                "decision_evidence_observation": {
                    "enabled": True,
                    "evidence": {
                        "evidence_level": "high",
                        "verify_confidence_labels": ["high"],
                        "web_hit_scores": ["missing"],
                        "no_gain": False,
                    },
                    "decision_events": [
                        {
                            "decision_type": "research_judge",
                            "judge_satisfies_request": True,
                        },
                        {
                            "decision_type": "research_progress",
                            "progress_action": "implement",
                            "progress_reason": "findings_complete",
                        },
                    ],
                },
            }
        ]
        cal = calibrate_from_rounds(rounds, run_meta={"pass": True, "case": "t"})
        self.assertEqual(cal["progress_action_counts"].get("implement"), 1)
        self.assertGreater(cal["web_decision_link_audit"]["candidates_total"], 0)
        audit = audit_code_linkage()
        self.assertFalse(audit["routing_on_web_score"])
        self.assertEqual(audit["linkage_before_kss12"], "missing")


if __name__ == "__main__":
    unittest.main()
