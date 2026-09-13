"""KSS-1.3 exploration value observation tests."""

import os
import unittest

from tools.ai.state.exploration_value import (
    ALWAYS_MISSING_FIELDS,
    attach_run_outcomes,
    empty_prior_sets,
    kss13_obs_enabled,
    observe_exploration_round,
    rebuild_from_round_details,
)


class Kss13ExplorationValueTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS13_OBS", None)
        os.environ.pop("AI_AGENT_KSS11_OBS", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KSS13_OBS", None)
        os.environ.pop("AI_AGENT_KSS11_OBS", None)
        os.environ.pop("AI_AGENT_KSS12_OBS", None)
        self.assertFalse(kss13_obs_enabled())

    def test_schema_and_missing_policy(self):
        os.environ["AI_AGENT_KSS13_OBS"] = "1"
        researched = {
            "web_hits": [
                {
                    "title": "Win32_OperatingSystem FreePhysicalMemory",
                    "snippet": "memory",
                    "url": "https://learn.microsoft.com/a",
                    "score": 2,
                }
            ],
            "candidates": [
                {
                    "command": "powershell",
                    "args": ["Get-WmiObject", "Win32_OperatingSystem"],
                }
            ],
            "knowledge_source_observation": {
                "known_coverage": {
                    "no_gain": False,
                    "has_gain": True,
                    "information_gain": {"has_gain": True, "no_gain": False},
                }
            },
            "decision_evidence_observation": {
                "enabled": True,
                "evidence": {
                    "evidence_level": "high",
                    "verify_high_count": 1,
                    "usable_count": 1,
                    "no_gain": False,
                },
            },
            "web_exec_stats": {
                "search_result_count": 5,
                "kept_hit_count": 1,
                "dropped_hit_count": 4,
                "web_hits_saved_count": 1,
            },
        }
        bundle, after = observe_exploration_round(
            round_num=1,
            researched=researched,
            progress_decision={
                "action": "implement",
                "reason": "findings_complete",
                "has_new_finding": True,
                "new_keys": [("cmd", "x")],
                "duplicate_only": False,
                "stagnation": 0,
            },
            prior_sets=empty_prior_sets(),
            case_id="memory_usage",
        )
        self.assertTrue(bundle["enabled"])
        self.assertTrue(bundle["not_for_decision"])
        self.assertFalse(bundle["behavior_changed"])
        self.assertEqual(bundle["search_volume"]["search_result_count"], 5)
        self.assertEqual(bundle["information_novelty"]["new_url_count"], 1)
        self.assertEqual(bundle["information_novelty"]["new_entity_count"], "missing")
        self.assertEqual(
            bundle["exploration_signal"]["composite_score"], "missing"
        )
        self.assertIn("new_entity_count", ALWAYS_MISSING_FIELDS)
        self.assertEqual(bundle["no_gain_existing"], False)
        self.assertIsInstance(bundle["information_gain_existing"], dict)
        self.assertGreater(bundle["exploration_leads"]["link_coverage"], 0)
        self.assertIn("learn.microsoft.com", after["hosts"])

    def test_round2_novelty_and_no_invented_search_count(self):
        prior = empty_prior_sets()
        prior["urls"].add("https://learn.microsoft.com/a")
        prior["hosts"].add("learn.microsoft.com")
        prior["tokens"] |= {"win32_operatingsystem", "freephysicalmemory"}
        bundle, _ = observe_exploration_round(
            round_num=2,
            researched={
                "web_hits": [
                    {
                        "title": "Win32_OperatingSystem FreePhysicalMemory",
                        "snippet": "same",
                        "url": "https://learn.microsoft.com/a",
                    }
                ],
                "candidates": [],
            },
            progress_decision={
                "action": "continue",
                "reason": "no_progress",
                "has_new_finding": False,
                "duplicate_only": True,
                "stagnation": 1,
            },
            prior_sets=prior,
            web_exec=None,
        )
        self.assertEqual(bundle["information_novelty"]["new_url_count"], 0)
        self.assertEqual(bundle["search_volume"]["search_result_count"], "missing")
        self.assertEqual(
            bundle["duplicate_or_repeated"]["progress_duplicate_only"], True
        )

    def test_attach_run_outcomes_next_round(self):
        bundles = [
            {
                "round_index": 1,
                "no_gain_existing": False,
                "information_novelty": {"new_term_count": 3},
                "run_linkage": {},
            },
            {
                "round_index": 2,
                "no_gain_existing": True,
                "information_gain_existing": {"has_gain": False},
                "information_novelty": {"new_term_count": 0},
                "run_linkage": {},
            },
        ]
        out = attach_run_outcomes(
            bundles, final_pass=False, fail_stage="research", fail_reason="stagnation"
        )
        self.assertTrue(out[0]["run_linkage"]["next_round_exists"])
        self.assertEqual(out[0]["run_linkage"]["next_round_gain"], False)
        self.assertFalse(out[1]["run_linkage"]["next_round_exists"])
        self.assertEqual(out[1]["run_linkage"]["final_pass"], False)
        self.assertEqual(out[1]["run_linkage"]["total_rounds"], 2)

    def test_rebuild_preserves_no_gain(self):
        details = [
            {
                "round": 1,
                "candidate_count": 1,
                "web_hits": [
                    {
                        "title": "Get-Volume disk",
                        "snippet": "usage",
                        "url": "https://example.com/disk",
                    }
                ],
                "verified_runs": [
                    {"command": "powershell", "args": ["Get-Volume"], "ok": False}
                ],
                "decision_evidence_observation": {
                    "enabled": True,
                    "evidence": {
                        "evidence_level": "medium",
                        "no_gain": True,
                        "usable_count": 0,
                    },
                    "decision_events": [
                        {
                            "decision_type": "research_progress",
                            "progress_action": "continue",
                            "progress_reason": "no_progress",
                            "progress_has_new_finding": False,
                            "progress_duplicate_only": True,
                            "progress_stagnation": 1,
                        }
                    ],
                },
                "knowledge_source_observation": {
                    "known_coverage": {"no_gain": True, "has_gain": False}
                },
            }
        ]
        bundles = rebuild_from_round_details(
            details, final_pass=False, fail_stage="research", case_id="disk_usage"
        )
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0]["no_gain_existing"], True)
        self.assertEqual(bundles[0]["run_linkage"]["case_id"], "disk_usage")

    def test_no_composite_score(self):
        b, _ = observe_exploration_round(
            round_num=1,
            researched={"web_hits": [], "candidates": []},
            progress_decision={"action": "stop", "reason": "stagnation"},
            prior_sets=empty_prior_sets(),
        )
        self.assertEqual(b["exploration_signal"]["composite_score"], "missing")


if __name__ == "__main__":
    unittest.main()
