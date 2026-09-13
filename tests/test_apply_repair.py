import unittest

from tools.system.tool_builder.apply import (
    REJECT_EMPTY_REPAIR_CODE,
    apply_repair,
    has_repair_code,
)
from tools.system.tool_builder.validate.implementation import (
    validate_tool_implementation,
)


PROPOSAL = {
    "name": "cpu_status",
    "module": "tools.system.cpu.cpu_status",
    "function": "cpu_status",
    "category": "system",
    "subcategory": "cpu",
    "output": ["status"],
}


class EmptyRepairCodeTests(unittest.TestCase):
    def test_has_repair_code_rejects_empty(self):
        self.assertFalse(has_repair_code({}))
        self.assertFalse(has_repair_code({"code": ""}))
        self.assertFalse(has_repair_code({"code": "   "}))
        self.assertTrue(has_repair_code({"code": "def cpu_status():\n    return {'status': '1'}\n"}))

    def test_validate_rejects_empty_code(self):
        result = validate_tool_implementation(
            PROPOSAL,
            {"path": "tools/system/cpu/cpu_status.py", "function": "cpu_status", "code": ""},
            registry=[{"name": "cpu_status"}],
            repair_mode=True,
        )
        self.assertEqual(result["result"], "NG")
        self.assertIn(REJECT_EMPTY_REPAIR_CODE, result["errors"][0])

    def test_apply_rejects_empty_code_even_if_validation_ok(self):
        result = apply_repair(
            "cpu_status",
            PROPOSAL,
            {
                "path": "tools/system/cpu/cpu_status.py",
                "function": "cpu_status",
                "code": "",
            },
            {"result": "OK"},
        )
        self.assertEqual(result["result"], "NG")
        self.assertIn(REJECT_EMPTY_REPAIR_CODE, result["errors"])


if __name__ == "__main__":
    unittest.main()
