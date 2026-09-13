import unittest

from tools.system.tool_builder.implementation_classify import (
    EMPTY_CODE,
    FINDING_NOT_USED,
    OK,
    UNNECESSARY_FINDING,
    WRONG_COMMAND,
    classify_implementation,
)
from tools.system.tool_builder.score import SCORING_VERSION, grade_for, score_implementation


FINDING_A = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse",
        ],
        "sample": ["43.2"],
    }
}
FINDING_B = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_PhysicalMemory | Select Capacity",
        ],
        "sample": ["16 GB"],
    }
}
FINDING_C = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize",
        ],
        "sample": ["16384 MB"],
    }
}
RESEARCH = {"usable_findings": [FINDING_B, FINDING_C, FINDING_A]}

CODE_A = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
CODE_A_C = """
import subprocess
def get_memory_status():
    total = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize'],
        capture_output=True, text=True)
    usage = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    return {'status': total.stdout.strip() + usage.stdout.strip()}
"""
CODE_B_C = """
import subprocess
def get_memory_status():
    capacity = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PhysicalMemory | Select Capacity'],
        capture_output=True, text=True)
    total = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize'],
        capture_output=True, text=True)
    return {'status': capacity.stdout.strip() + total.stdout.strip()}
"""


def scored(code=None, **kwargs):
    classified = classify_implementation(
        code=code,
        research_result=RESEARCH,
        expected_finding=FINDING_A,
        **kwargs,
    )
    return score_implementation(classified=classified, error=kwargs.get("error"))


class ImplementationScoreTests(unittest.TestCase):
    def test_grade_boundaries(self):
        self.assertEqual(grade_for(100), "S")
        self.assertEqual(grade_for(95), "S")
        self.assertEqual(grade_for(94), "A")
        self.assertEqual(grade_for(80), "B")
        self.assertEqual(grade_for(70), "C")
        self.assertEqual(grade_for(50), "D")
        self.assertEqual(grade_for(49), "F")

    def test_a_only_is_full_pass(self):
        result = scored(CODE_A)
        self.assertEqual(result["implementation_class"], OK)
        self.assertTrue(result["pass"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["grade"], "S")
        self.assertEqual(result["scoring_version"], SCORING_VERSION)
        self.assertEqual(result["score_breakdown"]["overimplementation"], 10)
        self.assertEqual(result["caps"], [])

    def test_a_plus_c_is_pass_with_mild_deduction(self):
        result = scored(CODE_A_C)
        self.assertEqual(result["implementation_class"], UNNECESSARY_FINDING)
        self.assertTrue(result["pass"])
        self.assertEqual(result["score"], 98)
        self.assertEqual(result["grade"], "S")
        self.assertEqual(result["score_breakdown"]["requirement"], 40)
        self.assertEqual(result["score_breakdown"]["overimplementation"], 8)

    def test_b_plus_c_is_partial_fail(self):
        result = scored(CODE_B_C)
        self.assertEqual(result["implementation_class"], FINDING_NOT_USED)
        self.assertFalse(result["pass"])
        self.assertEqual(result["score_breakdown"]["requirement"], 20)
        self.assertEqual(result["score"], 50)
        self.assertEqual(result["grade"], "D")
        self.assertEqual(result["caps"][0]["limit"], 69)

    def test_stub_is_unmet(self):
        result = scored("def get_memory_status():\n    return {'status': '未実装'}\n")
        self.assertEqual(result["implementation_class"], FINDING_NOT_USED)
        self.assertFalse(result["pass"])
        self.assertEqual(result["score"], 30)
        self.assertEqual(result["grade"], "F")

    def test_empty_code(self):
        result = scored(code="", error="no_json")
        self.assertEqual(result["implementation_class"], EMPTY_CODE)
        self.assertFalse(result["pass"])
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["grade"], "F")

    def test_invented_command_is_capped(self):
        code = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -ClassName Win32_MadeUp | Select PercentCommittedBytes'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        classified = classify_implementation(
            code=code,
            research_result={"usable_findings": [FINDING_A]},
            expected_finding=FINDING_A,
        )
        self.assertEqual(classified["class"], WRONG_COMMAND)
        result = score_implementation(classified=classified)
        self.assertFalse(result["pass"])
        self.assertEqual(result["score"], 25)
        self.assertEqual(result["caps"][0]["limit"], 49)

    def test_similar_other_purpose_is_partial_fail(self):
        finding_b = {
            "evidence": {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes",
                ],
                "sample": ["8192"],
            }
        }
        code = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        classified = classify_implementation(
            code=code,
            research_result={"usable_findings": [finding_b, FINDING_A]},
            expected_finding=FINDING_A,
        )
        result = score_implementation(classified=classified)
        self.assertEqual(classified["class"], FINDING_NOT_USED)
        self.assertFalse(result["pass"])
        self.assertEqual(result["score_breakdown"]["requirement"], 20)


if __name__ == "__main__":
    unittest.main()
