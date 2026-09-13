"""KSS-1.4 information loss + answer presence tests."""

import os
import unittest

from tools.ai.state.information_loss import (
    build_trajectory,
    detect_first_loss_point,
    observe_information_loss_round,
)
from tools.ai.state.web_answer_presence import (
    audit_round_answer_presence,
    collect_hit_partition_from_web_exec,
    heuristic_answer_presence,
    summarize_answer_presence,
)


class Kss14InformationLossTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS14_OBS", None)

    def test_chain_and_first_loss(self):
        k13 = {
            "enabled": True,
            "search_volume": {"kept_hit_count": 5, "search_result_count": "missing"},
            "exploration_leads": {
                "candidate_count": 3,
                "linked_candidate_count": 1,
                "zero_overlap_count": 2,
                "link_coverage": 0.33,
            },
            "information_novelty": {"new_term_count": 10, "new_source_count": 1},
            "evidence_strength": {
                "usable_count": 0,
                "verify_high_count": 0,
                "evidence_level": "medium",
            },
            "no_gain_existing": True,
            "information_gain_existing": {"has_gain": False, "no_gain": True},
            "progress_action": "continue",
            "progress_reason": "no_progress",
        }
        bundle = observe_information_loss_round(
            round_num=3,
            kss13_bundle=k13,
            round_item={
                "satisfies_request": False,
                "verified_runs": [{"ok": False}],
                "candidate_count": 3,
                "web_hits": [{"title": "t", "url": "https://x"}],
            },
            case_id="disk_usage",
        )
        self.assertTrue(bundle["enabled"])
        self.assertEqual(bundle["should_continue_web"], "missing")
        self.assertEqual(bundle["confidence_score"], "missing")
        self.assertEqual(len(bundle["chain"]), 9)
        self.assertEqual(
            bundle["first_loss_point"]["observational_label"], "VERIFICATION不足"
        )

    def test_memory_contrast_no_link_can_still_implement(self):
        traj = build_trajectory(
            case_id="memory_usage",
            rounds_kss13=[
                {
                    "round_index": 1,
                    "search_volume": {"kept_hit_count": 1},
                    "exploration_leads": {
                        "candidate_count": 4,
                        "linked_candidate_count": 0,
                        "link_coverage": 0.0,
                        "zero_overlap_count": 4,
                    },
                    "evidence_strength": {"usable_count": 1, "verify_high_count": 1},
                    "no_gain_existing": False,
                    "information_gain_existing": {"has_gain": True},
                    "progress_action": "implement",
                    "progress_reason": "findings_complete",
                    "information_novelty": {
                        "new_term_count": 47,
                        "new_source_count": 1,
                    },
                }
            ],
            round_details=[
                {
                    "round": 1,
                    "satisfies_request": True,
                    "verified_runs": [{"ok": True}],
                    "candidate_count": 4,
                    "web_hits": [{"title": "memory", "url": "https://learn.microsoft.com/a"}],
                }
            ],
            final_pass=True,
            fail_stage=None,
            stop_reason="findings_complete",
        )
        self.assertTrue(traj["final"]["success"])
        self.assertIn("success_trajectory", traj["run_loss_classification"]["labels"])

    def test_heuristic_core_and_unknown_not_none(self):
        core = heuristic_answer_presence(
            {
                "title": "Win32_OperatingSystem FreePhysicalMemory",
                "snippet": "TotalVisibleMemorySize property",
                "url": "https://learn.microsoft.com/os",
            },
            case_id="memory_usage",
            request_text="メモリ使用率",
        )
        self.assertIn(core["answer_presence"], ("direct", "core", "lead"))
        unk = heuristic_answer_presence(
            {"title": "", "snippet": "", "url": ""},
            case_id="memory_usage",
        )
        self.assertEqual(unk["answer_presence"], "unknown")

    def test_dropped_missing_not_invented(self):
        audit = audit_round_answer_presence(
            request_text="CPU温度",
            case_id="cpu_temperature",
            round_item={
                "web_hits": [
                    {
                        "title": "MSAcpi_ThermalZoneTemperature",
                        "snippet": "Get-CimInstance thermal zone",
                        "url": "https://example/thermal",
                    }
                ]
            },
        )
        self.assertEqual(audit["dropped_answer_presence"], "missing")
        self.assertEqual(audit["aggregates"]["answer_in_dropped_hit"], "missing")
        self.assertTrue(audit["not_llm_self_confidence"])
        self.assertEqual(audit["routing_hint"], "missing")

    def test_partition_from_web_exec(self):
        web_exec = {
            "results": [
                {
                    "hits": [
                        {"title": "kept", "snippet": "nvidia-smi memory.used", "url": "https://a"}
                    ],
                    "evidence": {
                        "dropped_hits": [
                            {
                                "title": "Exchange Online",
                                "snippet": "kerberos",
                                "url": "https://b",
                            }
                        ],
                        "dropped_count": 1,
                    },
                }
            ]
        }
        part = collect_hit_partition_from_web_exec(web_exec)
        self.assertEqual(part["kept_count"], 1)
        self.assertIsInstance(part["dropped_hits"], list)
        self.assertEqual(len(part["dropped_hits"]), 1)

    def test_valuable_dropped_flag(self):
        kept = [
            {
                "answer_presence": "related",
                "title": "x",
            }
        ]
        dropped = [
            {
                "answer_presence": "core",
                "discard_reason": "not_relevant_low_score",
                "title": "y",
            }
        ]
        summary = summarize_answer_presence(kept, dropped)
        self.assertTrue(summary["valuable_dropped_not_kept"])
        self.assertTrue(summary["answer_in_dropped_hit"])
        self.assertFalse(summary["answer_in_kept_hit"])


if __name__ == "__main__":
    unittest.main()
