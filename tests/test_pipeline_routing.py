import traceback
import unittest

from tests.fixtures import broken_tools
from tools.system.tool_builder.test import test_tool as run_registered_tool
from tools.system.tool_builder.validate.result import validate_tool_result
from tools.system.tool_builder.validate.warning_actions import (
    first_pipeline_step,
    is_blocked_on_info,
    needs_repair,
)


PROPOSAL = {
    "name": "cpu_status",
    "category": "system",
    "subcategory": "cpu",
    "output": ["status"],
}


def run_fixture(function):
    try:
        return {
            "result": "OK",
            "status": "pass",
            "return_value": function(),
            "error_type": None,
            "error": None,
        }
    except Exception as exc:
        return {
            "result": "NG",
            "status": "fail",
            "return_value": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def classify(
    test_result,
    proposal=None,
    implementation=None,
    research_result=None,
    source=None,
):
    validation = validate_tool_result(
        proposal or PROPOSAL,
        test_result,
        implementation=implementation,
        research_result=research_result,
        source=source,
    )
    return validation, first_pipeline_step(validation)


def repair_codes(validation):
    return [item["code"] for item in validation["disposition"]["repairable"]]


def blocked_codes(validation):
    return [item["code"] for item in validation["disposition"]["blocked"]]


class PipelineRoutingTests(unittest.TestCase):
    def test_pass_clean_value(self):
        validation, step = classify(run_fixture(broken_tools.pass_status))
        self.assertEqual(validation["status"], "pass")
        self.assertEqual(step, "pass")
        self.assertFalse(needs_repair(validation))
        self.assertFalse(is_blocked_on_info(validation))

    def test_repair_unparsed_output(self):
        validation, step = classify(
            run_fixture(broken_tools.repair_unparsed),
            source=broken_tools.SOURCE_UNPARSED,
        )
        self.assertEqual(step, "repair")
        self.assertIn("unparsed_output", repair_codes(validation))
        self.assertFalse(is_blocked_on_info(validation))
        item = next(
            entry
            for entry in validation["disposition"]["repairable"]
            if entry["code"] == "unparsed_output"
        )
        table = item["evidence"]["parsed_table"]["status"]
        self.assertEqual(table["header"], "LoadPercentage")
        self.assertEqual(table["separator"], "--------------")
        self.assertEqual(table["value"], "28")

    def test_repair_wrong_output_key(self):
        validation, step = classify(
            run_fixture(broken_tools.repair_missing_key),
            source=broken_tools.SOURCE_WRONG_KEY,
        )
        self.assertEqual(validation["status"], "warning")
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["wrong_output_key"])
        self.assertFalse(is_blocked_on_info(validation))

    def test_repair_return_value_not_dict(self):
        validation, step = classify(
            run_fixture(broken_tools.repair_not_dict),
            source=broken_tools.SOURCE_NOT_DICT,
        )
        self.assertEqual(validation["status"], "warning")
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["return_value_not_dict"])
        self.assertFalse(is_blocked_on_info(validation))

    def test_repair_subprocess_handling(self):
        validation, step = classify(
            run_fixture(broken_tools.repair_unparsed),
            source=broken_tools.SOURCE_SUBPROCESS_BAD,
        )
        self.assertEqual(step, "repair")
        self.assertIn("subprocess_result_handling", repair_codes(validation))
        self.assertFalse(is_blocked_on_info(validation))
        item = next(
            entry
            for entry in validation["disposition"]["repairable"]
            if entry["code"] == "subprocess_result_handling"
        )
        self.assertEqual(
            item["evidence"]["parsed_table"]["status"]["value"],
            "28",
        )

    def test_research_stub_value(self):
        validation, step = classify(
            run_fixture(broken_tools.research_stub),
            source=broken_tools.SOURCE_STUB,
        )
        self.assertEqual(validation["status"], "blocked")
        self.assertEqual(step, "research")
        self.assertEqual(blocked_codes(validation), ["stub_value"])
        self.assertFalse(needs_repair(validation))

    def test_stub_with_research_is_research_repair(self):
        validation, step = classify(
            run_fixture(broken_tools.research_stub),
            source=broken_tools.SOURCE_STUB,
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "research_repair")
        self.assertEqual(repair_codes(validation), ["stub_value"])
        self.assertTrue(needs_repair(validation))
        self.assertFalse(is_blocked_on_info(validation))

    def test_wrong_command_without_research(self):
        validation, step = classify(
            run_fixture(broken_tools.command_error_status),
            source=broken_tools.SOURCE_WRONG_COMMAND,
        )
        self.assertEqual(step, "pass")
        self.assertEqual(blocked_codes(validation), [])
        self.assertFalse(is_blocked_on_info(validation))

    def test_wrong_command_with_research_is_research_repair(self):
        validation, step = classify(
            run_fixture(broken_tools.command_error_status),
            source=broken_tools.SOURCE_WRONG_COMMAND,
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "research_repair")
        self.assertEqual(repair_codes(validation), ["wrong_command"])
        self.assertFalse(is_blocked_on_info(validation))

    def test_error_dict_without_research_does_not_imply_wrong_command(self):
        validation, step = classify(
            {"result": "OK", "return_value": {"status": "error"}},
            source=broken_tools.SOURCE_UNPARSED,
        )
        self.assertEqual(step, "pass")
        self.assertEqual(blocked_codes(validation), [])

    def test_repair_execution_error(self):
        validation, step = classify(run_fixture(broken_tools.execution_error))
        self.assertEqual(validation["status"], "fail")
        self.assertEqual(step, "repair")
        self.assertFalse(is_blocked_on_info(validation))

    def test_research_empty_output_spec(self):
        proposal = {**PROPOSAL, "output": []}
        validation, step = classify(
            run_fixture(broken_tools.pass_status),
            proposal=proposal,
        )
        self.assertEqual(step, "research")
        self.assertEqual(blocked_codes(validation), ["empty_output_spec"])

    def test_repair_missing_stub_marker(self):
        validation, step = classify(
            run_fixture(broken_tools.pass_status),
            implementation={"unimplemented": ["status"]},
        )
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["missing_stub_marker"])

    def test_repair_unconfirmed_looks_complete(self):
        proposal = {
            **PROPOSAL,
            "implementation_notes": ["個別メトリクスの取得可否は未確認"],
        }
        validation, step = classify(
            run_fixture(broken_tools.pass_status),
            proposal=proposal,
        )
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["unconfirmed_looks_complete"])

    def test_mixed_repair_first_then_research_remains(self):
        proposal = {**PROPOSAL, "output": ["status", "temp"]}
        validation, step = classify(
            run_fixture(broken_tools.mixed_unparsed_and_stub),
            proposal=proposal,
            source=broken_tools.SOURCE_UNPARSED,
        )
        self.assertEqual(step, "repair")
        self.assertTrue(needs_repair(validation))
        self.assertTrue(is_blocked_on_info(validation))
        self.assertIn("unparsed_output", repair_codes(validation))
        self.assertEqual(blocked_codes(validation), ["stub_value"])

    def test_repair_separator_value(self):
        validation, step = classify(run_fixture(broken_tools.separator_as_status))
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["meaningless_output"])

    def test_repair_empty_value(self):
        validation, step = classify(run_fixture(broken_tools.empty_status))
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["meaningless_output"])

    def test_repair_header_from_command_property(self):
        validation, step = classify(
            run_fixture(broken_tools.header_as_status),
            source=broken_tools.SOURCE_UNPARSED,
        )
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["meaningless_output"])

    def test_repair_header_from_research_sample(self):
        validation, step = classify(
            run_fixture(broken_tools.header_as_status),
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["meaningless_output"])

    def test_plain_string_status_still_passes(self):
        validation, step = classify(
            {"result": "OK", "return_value": {"status": "ok"}},
        )
        self.assertEqual(step, "pass")
        self.assertEqual(repair_codes(validation), [])

    def test_runtime_exception_keeps_self_heal_loop(self):
        test_result = {
            "result": "NG",
            "status": "fail",
            "return_value": None,
            "error_type": "IndexError",
            "error": "list index out of range",
            "traceback": "IndexError: list index out of range",
        }
        validation, step = classify(
            test_result,
            source=broken_tools.SOURCE_UNPARSED,
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "repair")
        self.assertEqual(repair_codes(validation), ["runtime_exception"])
        self.assertFalse(is_blocked_on_info(validation))
        self.assertTrue(needs_repair(validation))

    def test_registered_cpu_status_is_pass(self):
        test_result = run_registered_tool("cpu_status")
        validation, step = classify(test_result)
        self.assertEqual(test_result.get("result"), "OK")
        self.assertEqual(step, "pass")
        self.assertFalse(needs_repair(validation))
        self.assertFalse(is_blocked_on_info(validation))


if __name__ == "__main__":
    unittest.main()
