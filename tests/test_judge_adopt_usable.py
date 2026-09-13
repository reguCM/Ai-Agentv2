import unittest

from research.llm_benchmarks.judge_adopt_classify import inspect_judge_adopt_usable
from tools.ai.tool_builder.research_judge import create_research_judgment
from tools.system.llm_failure_memory import load_environment_case


class JudgeAdoptUsableTests(unittest.TestCase):
    def test_case_has_usable_percent_sample(self):
        case = load_environment_case("judge_usable_usage_percent")
        self.assertIsNotNone(case)
        usable = case["research_result"]["usable_findings"]
        self.assertEqual(len(usable), 1)
        self.assertEqual(usable[0]["evidence"]["sample"], ["48"])
        self.assertIn("TotalVisibleMemorySize", str(usable[0]["evidence"]["args"]))
        self.assertEqual(
            usable[0]["question"], "total physical memory is still unconfirmed"
        )
        self.assertEqual(case["state"]["decisions"][1]["value"], "Windowsのメモリ使用率")

    def test_materials_include_misleading_question_and_sample(self):
        from tools.ai.state.task_state import TaskState

        case = load_environment_case("judge_usable_usage_percent")
        state = TaskState.from_payload(case["state"])
        materials = create_research_judgment(
            case["request"],
            case["proposal"],
            case["research_result"],
            state=state,
        )
        self.assertEqual(len(materials["usable_findings"]), 1)
        finding = materials["usable_findings"][0]
        self.assertEqual(finding["sample"], ["48"])
        self.assertEqual(finding["question"], "total physical memory is still unconfirmed")
        self.assertTrue(materials.get("judging_hints"))

    def test_accept_payload_is_ok(self):
        held = inspect_judge_adopt_usable(
            {
                "satisfies_request": True,
                "reason": "sample は使用率の割合",
                "missing": [],
                "proposed_decisions": [{"key": "status.unit", "value": "%"}],
            }
        )
        self.assertTrue(held["ok"])
        self.assertEqual(held["grade"], "ACCEPT")

    def test_round3_misreject_payload(self):
        held = inspect_judge_adopt_usable(
            {
                "satisfies_request": False,
                "reason": "The sample provided is for total physical memory, not the memory usage percentage which is the metric requested.",
                "missing": ["used memory is still unconfirmed"],
            }
        )
        self.assertFalse(held["ok"])
        self.assertEqual(held["grade"], "MISREJECT")
        self.assertTrue(held["misreject"])

    def test_pipeline_round7_case_from_research_implement(self):
        case = load_environment_case("judge_usable_from_research_implement_round7")
        self.assertIsNotNone(case)
        self.assertEqual(case["pipeline_round"], 7)
        usable = case["research_result"]["usable_findings"]
        self.assertEqual(len(usable), 1)
        self.assertEqual(usable[0]["evidence"]["sample"], ["68719476736"])
        self.assertIn("Win32_PhysicalMemory", str(usable[0]["evidence"]["args"]))
        self.assertEqual(
            usable[0]["question"], "total physical memoryの正確な値"
        )
        self.assertFalse(case["pipeline_judge"]["satisfies_request"])

        from tools.ai.state.task_state import TaskState

        state = TaskState.from_payload(case["state"])
        materials = create_research_judgment(
            case["request"],
            case["proposal"],
            case["research_result"],
            state=state,
        )
        self.assertEqual(materials["usable_findings"][0]["sample"], ["68719476736"])
        self.assertNotIn("judging_hints", materials)

    def test_pipeline_round7_judge_payload_matches_misreject(self):
        case = load_environment_case("judge_usable_from_research_implement_round7")
        held = inspect_judge_adopt_usable(
            {
                "satisfies_request": case["pipeline_judge"]["satisfies_request"],
                "reason": case["pipeline_judge"]["reason"],
                "missing": case["pipeline_judge"]["missing"],
            },
            finding_question=case["research_result"]["usable_findings"][0]["question"],
        )
        self.assertEqual(held["grade"], "MISREJECT")
        self.assertFalse(held["ok"])

    def test_no_json_is_fail(self):
        held = inspect_judge_adopt_usable(None, error="no_json")
        self.assertFalse(held["ok"])
        self.assertEqual(held["grade"], "FAIL")


if __name__ == "__main__":
    unittest.main()
