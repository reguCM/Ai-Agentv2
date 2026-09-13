import unittest

from research.llm_benchmarks.judge_verify_retry_classify import inspect_judge_verify_retry
from tools.ai.tool_builder.research_judge import create_research_judgment
from tools.system.llm_failure_memory import load_environment_case


class JudgeVerifyRetryTests(unittest.TestCase):
    def test_case_is_failed_verify_not_usable_finding(self):
        case = load_environment_case("judge_verify_failed_retry")
        self.assertIsNotNone(case)
        research = case["research_result"]
        self.assertEqual(research.get("usable_findings"), [])
        unresolved = research.get("unresolved") or []
        self.assertEqual(len(unresolved), 1)
        evidence = unresolved[0]["evidence"]
        self.assertEqual(evidence.get("sample"), [])
        self.assertIn("0 で除算", evidence.get("error") or "")
        self.assertIn("-Command", evidence.get("args") or [])
        self.assertNotIn("TotalVisibleMemorySize", str(case))

    def test_judge_materials_show_empty_sample_and_error(self):
        case = load_environment_case("judge_verify_failed_retry")
        materials = create_research_judgment(
            case["request"],
            case["proposal"],
            case["research_result"],
        )
        self.assertEqual(materials["usable_findings"], [])
        unresolved = materials["unresolved"][0]
        self.assertEqual((unresolved.get("evidence") or {}).get("sample"), [])
        self.assertIn("0 で除算", unresolved.get("finding") or "")

    def test_json_missing_enables_retry_research(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "実行はしたが使用率の値が取れていない",
                "missing": ["メモリ使用率（使用中の割合）の取得方法"],
                "proposed_decisions": [],
            }
        )
        self.assertTrue(held["json_ok"])
        self.assertTrue(held["not_accepted"])
        self.assertTrue(held["has_missing"])
        self.assertTrue(held["retry_research"])
        self.assertTrue(held["retry_ok"])
        self.assertEqual(held["grade"], "B")
        self.assertFalse(held["ok"])

    def test_no_json_cannot_retry(self):
        held = inspect_judge_verify_retry(None, error="no_json")
        self.assertFalse(held["json_ok"])
        self.assertFalse(held["retry_research"])
        self.assertFalse(held["ok"])
        self.assertEqual(held["grade"], "FAIL")

    def test_accepting_failed_verify_is_not_ok(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": True,
                "reason": "command は実行された",
                "missing": [],
            }
        )
        self.assertFalse(held["not_accepted"])
        self.assertFalse(held["ok"])
        self.assertEqual(held["grade"], "FAIL")

    def test_empty_missing_cannot_retry(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "",
                "missing": [],
            }
        )
        self.assertFalse(held["has_missing"])
        self.assertFalse(held["retry_research"])
        self.assertFalse(held["ok"])
        self.assertEqual(held["grade"], "FAIL")

    def test_command_in_missing_is_not_a_question(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "計算に失敗した",
                "missing": [
                    "powershell -Command Get-WmiObject Win32_OperatingSystem"
                ],
            }
        )
        self.assertTrue(held["has_missing"])
        self.assertTrue(held["command_in_missing"])
        self.assertFalse(held["retry_ok"])
        self.assertEqual(held["grade"], "FAIL")


    def test_error_echo_in_missing_is_c(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "実環境で確認できなかった。0 で除算しようとしました。",
                "missing": ["実環境で確認できなかった。0 で除算しようとしました。"],
            }
        )
        self.assertTrue(held["retry_ok"])
        self.assertTrue(held["echo"])
        self.assertEqual(held["grade"], "C")
        self.assertFalse(held["ok"])

    def test_gap_targets_without_class_name_is_a(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "現在の候補では使用率を計算できない",
                "missing": [
                    "総物理メモリを取得する方法が未確認",
                    "使用中メモリを取得する方法が未確認",
                ],
            }
        )
        self.assertTrue(held["retry_ok"])
        self.assertTrue(held["has_gap"])
        self.assertFalse(held["vague"])
        self.assertEqual(held["grade"], "A")
        self.assertTrue(held["ok"])
        self.assertNotIn("Win32", str(held))

    def test_vague_command_script_missing_is_b(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "0 で除算した",
                "missing": [
                    "正しい方法でメモリ使用率を取得するためのコマンドやスクリプトを調べてください。"
                ],
            }
        )
        self.assertTrue(held["vague"])
        self.assertEqual(held["grade"], "B")

    def test_english_gap_missing_is_a(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "division by zero",
                "missing": [
                    "total physical memory is still unconfirmed",
                    "used memory is still unconfirmed",
                ],
            }
        )
        self.assertTrue(held["has_gap"])
        self.assertFalse(held["vague"])
        self.assertEqual(held["grade"], "A")
        self.assertTrue(held["ok"])

    def test_failure_case_materials_include_verify_hints(self):
        from tools.ai.state.task_state import TaskState

        case = load_environment_case("judge_verify_failed_retry")
        state = TaskState.from_payload(case["state"])
        materials = create_research_judgment(
            case["request"],
            case["proposal"],
            case["research_result"],
            state=state,
        )
        hints = " ".join(materials.get("judging_hints") or [])
        self.assertIn("verify failure", hints.lower())
        self.assertIn("measurement targets", hints.lower())

    def test_vague_method_only_is_b(self):
        held = inspect_judge_verify_retry(
            {
                "satisfies_request": False,
                "reason": "実行エラーが発生している",
                "missing": ["メモリ使用率の取得方法を確認する必要があります"],
            }
        )
        self.assertTrue(held["retry_ok"])
        self.assertFalse(held["has_gap"])
        self.assertTrue(held["vague"])
        self.assertEqual(held["grade"], "B")
        self.assertFalse(held["ok"])


if __name__ == "__main__":
    unittest.main()
