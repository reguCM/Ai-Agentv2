import unittest

from research.llm_benchmarks.judge_regression import (
    BASELINES,
    JUDGE_CONTRACT_PHASE,
    check_baseline_files,
    compare_entry_to_baseline,
    load_baseline,
)


class JudgeRegressionBaselineTests(unittest.TestCase):
    def test_baseline_files_exist_and_match_contract(self):
        errors = check_baseline_files()
        self.assertEqual(errors, [])

    def test_verify_retry_baseline_is_a_3_of_3(self):
        baseline = load_baseline("verify_retry")
        self.assertEqual(baseline["pass_criterion"], "A")
        self.assertEqual(baseline["trial_grades"], ["A", "A", "A"])
        self.assertEqual(baseline["grades"], {"A": 3})
        self.assertEqual(baseline["contract_phase"], JUDGE_CONTRACT_PHASE)
        self.assertEqual(baseline["case"], "judge_verify_failed_retry")
        self.assertNotIn("正しい方法", str(baseline.get("missing_examples")))

    def test_adopt_baseline_is_accept_3_of_3(self):
        baseline = load_baseline("adopt_usable")
        self.assertEqual(baseline["pass_criterion"], "ACCEPT")
        self.assertEqual(baseline["trial_grades"], ["ACCEPT", "ACCEPT", "ACCEPT"])
        self.assertEqual(baseline["grades"], {"ACCEPT": 3})
        self.assertEqual(baseline["contract_phase"], JUDGE_CONTRACT_PHASE)
        self.assertEqual(baseline["case"], "judge_usable_usage_percent")
        self.assertTrue(baseline.get("misreject_forbidden"))

    def test_compare_entry_rejects_regression(self):
        baseline = load_baseline("verify_retry")
        bad = {
            "contract_phase": JUDGE_CONTRACT_PHASE,
            "pass_criterion": "A",
            "case": "judge_verify_failed_retry",
            "pass": False,
            "grades": {"B": 3},
            "trials": [
                {"n": 1, "held": {"grade": "B"}},
                {"n": 2, "held": {"grade": "B"}},
                {"n": 3, "held": {"grade": "B"}},
            ],
        }
        errors = compare_entry_to_baseline(bad, baseline)
        self.assertTrue(errors)

    def test_baseline_paths_are_under_benchmarks_dir(self):
        for spec in BASELINES.values():
            self.assertTrue(spec["baseline_path"].exists())
            self.assertIn("baseline", spec["baseline_path"].name)


if __name__ == "__main__":
    unittest.main()
