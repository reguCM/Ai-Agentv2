import unittest

from research.llm_benchmarks.persistence_classify import (
    all_recognized,
    classify_status_unit,
)


class StatusUnitClassifyTests(unittest.TestCase):
    def test_percent_only(self):
        labels = classify_status_unit("%")
        self.assertFalse(labels["recognized_memory_usage"])
        self.assertFalse(labels["recognized_tool_status"])
        self.assertTrue(labels["unit_percent"])
        self.assertFalse(all_recognized(labels))

    def test_memory_and_percent(self):
        labels = classify_status_unit("メモリ使用率なので単位は%")
        self.assertTrue(labels["recognized_memory_usage"])
        self.assertFalse(labels["recognized_tool_status"])
        self.assertTrue(labels["unit_percent"])

    def test_tool_value_and_percent(self):
        labels = classify_status_unit("今回のToolの戻り値 43.2 の単位は%")
        self.assertFalse(labels["recognized_memory_usage"])
        self.assertTrue(labels["recognized_tool_status"])
        self.assertTrue(labels["unit_percent"])

    def test_all_three(self):
        labels = classify_status_unit(
            "今回のToolのstatus 43.2はメモリ使用率なので単位は%"
        )
        self.assertTrue(all_recognized(labels))

    def test_generic_http_status(self):
        labels = classify_status_unit("HTTP status code has no unit")
        self.assertFalse(labels["recognized_memory_usage"])
        self.assertFalse(labels["recognized_tool_status"])
        self.assertFalse(labels["unit_percent"])
        self.assertTrue(labels["generic_status"])

    def test_state_wording_counts_as_memory(self):
        labels = classify_status_unit(
            "STATEどおり status はWindowsのメモリ使用率で単位は%"
        )
        self.assertTrue(labels["recognized_memory_usage"])
        self.assertTrue(labels["unit_percent"])

    def test_reason_value_inference(self):
        labels = classify_status_unit("43.2なので単位は%")
        self.assertEqual(labels["reason_class"], "value_inference")
        self.assertTrue(labels["unit_percent"])
        self.assertFalse(labels["recognized_memory_usage"])

    def test_reason_state_based_when_state_present(self):
        labels = classify_status_unit(
            "The tool returned a memory usage rate in percentage format.",
            state_present=True,
        )
        self.assertEqual(labels["reason_class"], "state_based")
        self.assertTrue(labels["recognized_memory_usage"])

    def test_reason_memory_without_state_is_general(self):
        labels = classify_status_unit(
            "メモリ使用率なので単位は%",
            state_present=False,
        )
        self.assertEqual(labels["reason_class"], "general_knowledge")

    def test_reason_explicit_state_keys(self):
        labels = classify_status_unit(
            "status.unit が % で range は 0-100",
            state_present=False,
        )
        self.assertEqual(labels["reason_class"], "state_based")

    def test_reason_unknown_bare_percent(self):
        labels = classify_status_unit("%")
        self.assertEqual(labels["reason_class"], "unknown")


class GapStateInspectTests(unittest.TestCase):
    def test_without_state_is_not_lost(self):
        from research.llm_benchmarks.persistence_benchmark import inspect_state

        report = inspect_state(None, with_state=False)
        self.assertFalse(report["injected"])
        self.assertFalse(report["lost"])

    def test_with_state_keeps_keys(self):
        from research.llm_benchmarks.persistence_benchmark import inspect_state
        from tools.ai.state.task_state import TaskState
        from tools.system.llm_failure_memory import load_environment_case

        case = load_environment_case("persist_unit_gap")
        state = TaskState.from_payload(case["state"])
        report = inspect_state(state, with_state=True)
        self.assertTrue(report["injected"])
        self.assertFalse(report["lost"])
        self.assertIn("status.unit", report["keys"])

    def test_missing_decision_is_lost(self):
        from research.llm_benchmarks.persistence_benchmark import inspect_state
        from tools.ai.state.task_state import TaskState

        state = TaskState(task="t")
        report = inspect_state(state, with_state=True)
        self.assertTrue(report["lost"])
