"""KSS-1.5 web hit partition + human audit dataset tests."""

import os
import unittest

from tools.ai.state.web_hit_partition import (
    build_human_audit_dataset,
    build_search_partition,
    compute_kss15_metrics,
    kss15_obs_enabled,
    merge_web_exec_partitions,
    track_lead_trajectories,
)


class Kss15WebHitPartitionTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KSS15_OBS", None)
        os.environ.pop("AI_AGENT_KSS14_OBS", None)

    def test_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KSS15_OBS", None)
        os.environ.pop("AI_AGENT_KSS14_OBS", None)
        self.assertFalse(kss15_obs_enabled())

    def test_partition_separates_kept_dropped(self):
        ranked = [
            {
                "title": "Win32_LogicalDisk FreeSpace",
                "snippet": "Get-CimInstance disk usage",
                "url": "https://learn.microsoft.com/disk",
                "backend": "learn.microsoft",
            },
            {
                "title": "Exchange Online kerberos",
                "snippet": "unrelated",
                "url": "https://example.com/ex",
                "backend": "web",
            },
        ]
        part = build_search_partition(
            ranked_hits=ranked,
            kept_hits=[ranked[0]],
            dropped_irrelevant=[ranked[1]],
            query="disk usage windows",
            round_id=1,
        )
        self.assertEqual(part["kept_count"], 1)
        self.assertEqual(part["dropped_count"], 1)
        kept = [r for r in part["records"] if r["kept"]]
        dropped = [r for r in part["records"] if not r["kept"]]
        self.assertTrue(kept[0]["url"].endswith("/disk"))
        self.assertEqual(dropped[0]["kept"], False)
        self.assertNotEqual(dropped[0]["drop_reason"], "kept")
        self.assertIn("query", kept[0])
        self.assertIn("hit_id", kept[0])

    def test_do_not_invent_dropped_without_web_exec(self):
        part = merge_web_exec_partitions(None)
        self.assertEqual(part["dropped_hits"], "missing")

    def test_human_audit_buckets_and_metrics(self):
        cases = [
            {
                "case": "disk_usage",
                "pass": False,
                "fail_stage": "research",
                "stop_reason": "stagnation",
                "request": "ディスク使用率",
                "rounds": [
                    {
                        "round": 1,
                        "web_hit_partition": {
                            "source": "live_web_exec",
                            "total_searches": 1,
                            "dropped_hits": [{"url": "x"}],
                            "records": [
                                {
                                    "kept": False,
                                    "drop_reason": "not_relevant_low_score",
                                    "url": "https://a",
                                    "title": "Win32_LogicalDisk FreeSpace",
                                    "snippet": "freespace",
                                    "heuristic_answer_presence": "core",
                                    "human_answer_presence": "missing",
                                },
                                {
                                    "kept": True,
                                    "drop_reason": "kept",
                                    "url": "https://b",
                                    "title": "other",
                                    "snippet": "x",
                                    "heuristic_answer_presence": "related",
                                    "human_answer_presence": "missing",
                                },
                            ],
                        },
                        "exploration_value_observation": {"no_gain_existing": True},
                    }
                ],
            },
            {
                "case": "memory_usage",
                "pass": True,
                "request": "メモリ使用率",
                "rounds": [
                    {
                        "round": 1,
                        "web_hit_partition": {
                            "source": "live_web_exec",
                            "total_searches": 1,
                            "dropped_hits": [],
                            "records": [
                                {
                                    "kept": True,
                                    "drop_reason": "kept",
                                    "url": "https://c",
                                    "title": "FreePhysicalMemory",
                                    "snippet": "TotalVisibleMemorySize",
                                    "heuristic_answer_presence": "core",
                                    "human_answer_presence": "missing",
                                },
                                {
                                    "kept": False,
                                    "drop_reason": "irrelevant_token:kerberos",
                                    "url": "https://d",
                                    "title": "Exchange",
                                    "snippet": "kerberos",
                                    "heuristic_answer_presence": "none",
                                    "human_answer_presence": "missing",
                                },
                            ],
                        },
                    }
                ],
            },
        ]
        ds = build_human_audit_dataset(cases)
        self.assertGreater(len(ds["entries"]), 0)
        self.assertIn("A_failed_dropped", ds["bucket_counts"])
        metrics = compute_kss15_metrics(cases)
        self.assertEqual(metrics["failed_runs_with_answer_in_dropped"], 1)
        self.assertNotEqual(metrics["dropped_answer_rate"], "missing")
        self.assertEqual(
            metrics["llm_judge_agreement"]["status"], "deferred_until_human_labels"
        )

    def test_lead_tracking(self):
        cases = [
            {
                "case": "cpu_temperature",
                "pass": False,
                "rounds": [
                    {
                        "round": 1,
                        "web_hit_partition": {
                            "records": [
                                {
                                    "kept": True,
                                    "heuristic_answer_presence": "lead",
                                    "human_answer_presence": "missing",
                                }
                            ]
                        },
                        "exploration_value_observation": {"no_gain_existing": False},
                    },
                    {
                        "round": 2,
                        "web_hit_partition": {
                            "records": [
                                {
                                    "kept": True,
                                    "heuristic_answer_presence": "related",
                                    "human_answer_presence": "missing",
                                }
                            ]
                        },
                        "exploration_value_observation": {"no_gain_existing": True},
                    },
                    {
                        "round": 3,
                        "web_hit_partition": {"records": []},
                        "exploration_value_observation": {"no_gain_existing": True},
                    },
                ],
            }
        ]
        tracks = track_lead_trajectories(cases)
        self.assertEqual(tracks[0]["pattern"], "lead_then_no_gain")


if __name__ == "__main__":
    unittest.main()
