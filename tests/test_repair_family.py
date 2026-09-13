import unittest

from tests.fixtures import broken_tools
from tests.test_pipeline_routing import classify, repair_codes, blocked_codes, run_fixture
from tools.system.tool_builder.repair_family import (
    R1,
    R2,
    R3,
    R4,
    R5,
    classify_repair_family,
)


class RepairFamilyTests(unittest.TestCase):
    def test_code_mapping(self):
        self.assertEqual(classify_repair_family(codes=["return_value_not_dict"]), R1)
        self.assertEqual(classify_repair_family(codes=["runtime_exception"]), R2)
        self.assertEqual(classify_repair_family(codes=["semantic_mismatch"]), R3)
        self.assertEqual(classify_repair_family(codes=["wrong_command"]), R4)
        self.assertEqual(classify_repair_family(codes=["stub_value"]), R5)

    def test_empty_code_and_broken_json_are_r1(self):
        self.assertEqual(classify_repair_family(error="no_json"), R1)
        self.assertEqual(classify_repair_family(error="no_code"), R1)

    def test_runtime_outranks_format(self):
        self.assertEqual(
            classify_repair_family(codes=["unparsed_output", "runtime_exception"]),
            R2,
        )

    def test_r1_empty_body_is_return_format(self):
        validation, step = classify(run_fixture(broken_tools.empty_body))
        self.assertEqual(step, "repair")
        self.assertIn("return_value_not_dict", repair_codes(validation))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R1)

    def test_r1_wrong_key(self):
        validation, step = classify(
            run_fixture(broken_tools.repair_missing_key),
            source=broken_tools.SOURCE_WRONG_KEY,
        )
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R1)
        self.assertEqual(step, "repair")

    def test_r2_index_error(self):
        validation, step = classify(run_fixture(broken_tools.index_error_status))
        self.assertEqual(step, "repair")
        self.assertIn("runtime_exception", repair_codes(validation))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R2)

    def test_r2_key_error(self):
        validation, step = classify(run_fixture(broken_tools.key_error_status))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R2)

    def test_r2_type_error(self):
        validation, step = classify(run_fixture(broken_tools.type_error_status))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R2)

    def test_r3_runs_but_wrong_kind_of_value(self):
        validation, step = classify(
            run_fixture(broken_tools.semantic_name_as_status),
            source=broken_tools.SOURCE_SEMANTIC,
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "repair")
        self.assertIn("semantic_mismatch", repair_codes(validation))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R3)

    def test_r4_wrong_finding_with_research(self):
        validation, step = classify(
            run_fixture(broken_tools.command_error_status),
            source=broken_tools.SOURCE_WRONG_COMMAND,
            research_result=broken_tools.VERIFIED_RESEARCH,
        )
        self.assertEqual(step, "research_repair")
        self.assertIn("wrong_command", repair_codes(validation))
        self.assertEqual(classify_repair_family(codes=repair_codes(validation)), R4)

    def test_r5_stub_needs_research(self):
        validation, step = classify(
            run_fixture(broken_tools.research_stub),
            source=broken_tools.SOURCE_STUB,
        )
        self.assertEqual(step, "research")
        self.assertEqual(blocked_codes(validation), ["stub_value"])
        self.assertEqual(
            classify_repair_family(codes=blocked_codes(validation), step=step),
            R5,
        )


if __name__ == "__main__":
    unittest.main()
