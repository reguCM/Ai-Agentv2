import tempfile
import unittest
from pathlib import Path

from research.llm_benchmarks import history


SAMPLE_RUNS = [
    {
        "timestamp": "2026-08-18T15:00:00+00:00",
        "case": "implement_from_verified_memory_finding",
        "profile": "qwen3_8b",
        "model": "qwen3:8b",
        "n": 1,
        "pass": True,
        "score": 100,
        "grade": "S",
        "scoring_version": "1.0",
        "implementation_class": {"class": "ok"},
    },
    {
        "timestamp": "2026-08-18T15:01:00+00:00",
        "case": "implement_choose_usage_among_memory_findings",
        "profile": "qwen3_8b",
        "model": "qwen3:8b",
        "n": 1,
        "pass": True,
        "score": 100,
        "grade": "S",
        "scoring_version": "1.0",
        "implementation_class": {"class": "ok"},
    },
    {
        "timestamp": "2026-08-18T15:02:00+00:00",
        "case": "implement_choose_usage_among_memory_findings",
        "profile": "qwen2_5_coder_7b",
        "model": "qwen2.5-coder:7b",
        "n": 1,
        "pass": True,
        "score": 98,
        "grade": "S",
        "scoring_version": "1.0",
        "implementation_class": {
            "class": "unnecessary_finding",
            "used_other": ["Win32_OperatingSystem"],
        },
    },
]


class BenchmarkHistoryTests(unittest.TestCase):
    def test_compact_run_drops_code(self):
        compact = history.compact_run(
            {
                **SAMPLE_RUNS[0],
                "generated_code": "def get_memory_status(): pass",
            }
        )
        self.assertNotIn("generated_code", compact)
        self.assertTrue(compact["pass"])
        self.assertEqual(compact["score"], 100)
        self.assertEqual(compact["class"], "ok")
        self.assertEqual(compact["case"], "implement_from_verified_memory_finding")

    def test_compact_run_keeps_timing(self):
        compact = history.compact_run(
            {
                **SAMPLE_RUNS[0],
                "timing": {
                    "total_seconds": 12.3,
                    "llm_seconds": 11.0,
                    "machine_seconds": 1.3,
                    "implementation_seconds": 12.1,
                },
            }
        )
        self.assertEqual(compact["timing"]["total_seconds"], 12.3)
        self.assertEqual(compact["timing"]["llm_seconds"], 11.0)

    def test_compact_run_scores_missing_fields(self):
        compact = history.compact_run(
            {
                "case": "implement_choose_usage_among_memory_findings",
                "profile": "qwen2_5_coder_7b",
                "implementation_class": {
                    "class": "unnecessary_finding",
                    "finding_adopted": True,
                    "used_other": ["Win32_OperatingSystem"],
                    "has_fetch_call": True,
                },
            }
        )
        self.assertTrue(compact["pass"])
        self.assertEqual(compact["score"], 98)
        self.assertEqual(compact["class"], "unnecessary_finding")

    def test_summarize_by_case_and_model(self):
        compact = [history.compact_run(item) for item in SAMPLE_RUNS]
        summary = history.summarize(compact)
        choose = summary["by_case"]["implement_choose_usage_among_memory_findings"]
        self.assertEqual(choose["qwen3_8b"]["runs"], 1)
        self.assertEqual(choose["qwen3_8b"]["avg_score"], 100)
        self.assertEqual(choose["qwen2_5_coder_7b"]["avg_score"], 98)
        self.assertEqual(choose["qwen2_5_coder_7b"]["classes"]["unnecessary_finding"], 1)
        model = summary["by_model"]["qwen3_8b"]
        self.assertEqual(len(model), 2)
        self.assertEqual(
            model["implement_from_verified_memory_finding"]["pass"], 1
        )

    def test_refresh_writes_history_and_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            history_path = root / "history.json"
            summary_path = root / "summary.json"
            old_history = history.HISTORY_PATH
            old_summary = history.SUMMARY_PATH
            history.HISTORY_PATH = history_path
            history.SUMMARY_PATH = summary_path
            try:
                summary = history.refresh_history(results={"runs": SAMPLE_RUNS})
                self.assertEqual(summary["runs"], 3)
                saved = history.load_json_file(history_path, {})
                self.assertEqual(len(saved["runs"]), 3)
                self.assertNotIn("generated_code", saved["runs"][0])
                text = history.format_summary(summary)
                self.assertIn("implement_choose_usage_among_memory_findings", text)
                self.assertIn("qwen2_5_coder_7b", text)
                self.assertIn("unnecessary_finding:1", text)
            finally:
                history.HISTORY_PATH = old_history
                history.SUMMARY_PATH = old_summary


if __name__ == "__main__":
    unittest.main()
