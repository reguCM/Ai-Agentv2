import unittest

from tests.fixtures import broken_tools
from tools.ai.tool_builder.repair import select_repair_materials
from tools.system.llm_failure_memory import (
    environment_patterns,
    failures_for,
    ignored_research_implementation,
    patterns_for,
)
from tools.system.tool_builder.validate.result import parse_tabular_text
from tools.system.tool_builder.validate.warning_actions import first_pipeline_step
from tools.system.tool_builder.validate.result import validate_tool_result


class TableParseTests(unittest.TestCase):
    def test_powershell_table_to_header_separator_value(self):
        parsed = parse_tabular_text(
            "LoadPercentage\n--------------\n            28"
        )
        self.assertEqual(parsed["header"], "LoadPercentage")
        self.assertEqual(parsed["separator"], "--------------")
        self.assertEqual(parsed["value"], "28")

    def test_research_sample_lines(self):
        parsed = parse_tabular_text("\n".join(["LoadPercentage", "--------------", "38"]))
        self.assertEqual(parsed["value"], "38")

    def test_not_a_table(self):
        self.assertIsNone(parse_tabular_text("28"))

    def test_unparsed_warning_carries_parsed_table(self):
        validation = validate_tool_result(
            {"output": ["status"]},
            {
                "result": "OK",
                "return_value": {
                    "status": "LoadPercentage\n--------------\n            28"
                },
            },
            source=broken_tools.SOURCE_UNPARSED,
        )
        self.assertEqual(first_pipeline_step(validation), "repair")
        item = validation["disposition"]["repairable"][0]
        self.assertEqual(item["code"], "unparsed_output")
        table = item["evidence"]["parsed_table"]["status"]
        self.assertEqual(table["header"], "LoadPercentage")
        self.assertEqual(table["value"], "28")

    def test_research_sample_is_structured_in_materials(self):
        materials = select_repair_materials(
            {
                "tool_name": "cpu_status",
                "current_source": broken_tools.SOURCE_STUB,
                "target_path": "tools/system/cpu/cpu_status.py",
                "target_function": "cpu_status",
                "target_output": ["status"],
                "repairable_warnings": [
                    {
                        "code": "stub_value",
                        "needs_research_findings": True,
                    }
                ],
                "test_result": {"result": "OK", "return_value": {"status": "未実装"}},
                "research_result": broken_tools.VERIFIED_RESEARCH,
            }
        )
        table = materials["research_result"]["usable_findings"][0]["evidence"][
            "parsed_table"
        ]
        self.assertEqual(table["header"], "LoadPercentage")
        self.assertEqual(table["value"], "38")
        self.assertNotIn("parsed_table", broken_tools.VERIFIED_RESEARCH["usable_findings"][0]["evidence"])


class FailureMemoryTests(unittest.TestCase):
    def test_deepseek_has_stub_echo_memory(self):
        self.assertTrue(ignored_research_implementation("deepseek_coder_v2_16b"))
        self.assertFalse(ignored_research_implementation("qwen3_8b"))

    def test_table_parse_pattern_is_listed(self):
        items = patterns_for(
            "deepseek_coder_v2_16b",
            repair_type="unparsed_output",
        )
        self.assertTrue(any(item["id"] == "powershell_table_fixed_index" for item in items))

    def test_failures_are_queryable_without_wiring_repair(self):
        entries = failures_for(
            "deepseek_coder_v2_16b",
            repair_type="stub_value",
            failure_pattern="stub_not_implemented",
        )
        self.assertTrue(entries)

    def test_environment_insufficient_research_is_catalogued(self):
        items = environment_patterns(class_name="research_misses_request")
        self.assertTrue(
            any(item["id"] == "insufficient_research_memory_capacity" for item in items)
        )


if __name__ == "__main__":
    unittest.main()
