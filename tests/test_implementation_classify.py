import unittest

from tools.system.llm_failure_memory import load_environment_case
from tools.system.tool_builder.implementation_classify import (
    EMPTY_CODE,
    FINDING_NOT_USED,
    OK,
    UNNECESSARY_FINDING,
    WRONG_COMMAND,
    classify_implementation,
    distinctive_fragments,
    uses_finding,
)


FINDING = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse",
        ],
        "sample": ["PercentCommittedBytesInUse", "--------------------------", "39"],
    }
}

RESEARCH = {"usable_findings": [FINDING]}


class ImplementationClassifyTests(unittest.TestCase):
    def test_fragments_skip_generic_flags(self):
        fragments = distinctive_fragments(FINDING)
        self.assertIn("Win32_PerfFormattedData_PerfOS_Memory", fragments)
        self.assertIn("PercentCommittedBytesInUse", fragments)
        self.assertNotIn("powershell", fragments)
        self.assertNotIn("-NoProfile", fragments)

    def test_empty_code(self):
        decision = classify_implementation(
            payload={"code": "", "unimplemented": ["status"]},
            research_result=RESEARCH,
        )
        self.assertEqual(decision["class"], EMPTY_CODE)

    def test_no_json_is_empty_code(self):
        decision = classify_implementation(
            error="no_json",
            payload=None,
            research_result=RESEARCH,
        )
        self.assertEqual(decision["class"], EMPTY_CODE)

    def test_stub_does_not_use_finding(self):
        decision = classify_implementation(
            payload={"code": "def get_memory_status():\n    return {'status': '未実装'}\n"},
            research_result=RESEARCH,
        )
        self.assertEqual(decision["class"], FINDING_NOT_USED)
        self.assertFalse(decision["finding_adopted"])

    def test_different_command(self):
        code = """
import subprocess
def get_memory_status():
    result = subprocess.run([
        'powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object -ExpandProperty PercentCommittedBytes'
    ], capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        decision = classify_implementation(code=code, research_result=RESEARCH)
        self.assertEqual(decision["class"], WRONG_COMMAND)
        self.assertFalse(uses_finding(code, FINDING))

    def test_uses_finding_command(self):
        code = """
import subprocess
def get_memory_status():
    result = subprocess.run([
        'powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'
    ], capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        decision = classify_implementation(
            payload={"code": code},
            research_result=RESEARCH,
        )
        self.assertEqual(decision["class"], OK)
        self.assertTrue(decision["finding_adopted"])

    def test_picks_usage_not_capacity_among_similar_findings(self):
        finding_b = {
            "evidence": {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-CimInstance -Class Win32_PhysicalMemory | Select Capacity",
                ],
                "sample": ["16 GB"],
            }
        }
        finding_c = {
            "evidence": {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize",
                ],
                "sample": ["16384 MB"],
            }
        }
        research = {"usable_findings": [finding_b, finding_c, FINDING]}
        uses_b = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PhysicalMemory | Select Capacity'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_c = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_a = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_a_and_c = """
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
        uses_b_and_c = """
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
        self.assertEqual(
            classify_implementation(
                code=uses_b,
                research_result=research,
                expected_finding=FINDING,
            )["class"],
            FINDING_NOT_USED,
        )
        self.assertEqual(
            classify_implementation(
                code=uses_c,
                research_result=research,
                expected_finding=FINDING,
            )["class"],
            FINDING_NOT_USED,
        )
        self.assertEqual(
            classify_implementation(
                code=uses_a,
                research_result=research,
                expected_finding=FINDING,
            )["class"],
            OK,
        )
        self.assertEqual(
            classify_implementation(
                code=uses_a_and_c,
                research_result=research,
                expected_finding=FINDING,
            )["class"],
            UNNECESSARY_FINDING,
        )
        self.assertEqual(
            classify_implementation(
                code=uses_b_and_c,
                research_result=research,
                expected_finding=FINDING,
            )["class"],
            FINDING_NOT_USED,
        )

    def test_similar_candidates_only_complete_match_is_ok(self):
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
        finding_c = {
            "evidence": {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-WmiObject -Class Win32_OperatingSystem | Select TotalVisibleMemorySize",
                ],
                "sample": ["16384"],
            }
        }
        finding_d = {
            "evidence": {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-CimInstance -Class Win32_OperatingSystem | Select FreePhysicalMemory",
                ],
                "sample": ["9342000"],
            }
        }
        research = {"usable_findings": [finding_b, finding_c, finding_d, FINDING]}
        uses_b = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_c = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-WmiObject -Class Win32_OperatingSystem | Select TotalVisibleMemorySize'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_d = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select FreePhysicalMemory'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_a = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        uses_a_and_b = uses_a + "\nAvailableMBytes = 0\n"
        for code, expected in (
            (uses_b, FINDING_NOT_USED),
            (uses_c, FINDING_NOT_USED),
            (uses_d, FINDING_NOT_USED),
            (uses_a, OK),
            (uses_a_and_b, UNNECESSARY_FINDING),
        ):
            self.assertEqual(
                classify_implementation(
                    code=code,
                    research_result=research,
                    expected_finding=FINDING,
                )["class"],
                expected,
            )


class SimilarCandidatesCaseTests(unittest.TestCase):
    def test_case_expected_fragment_matches_only_complete_finding(self):
        case = load_environment_case("implement_similar_memory_candidates")
        marker = case["correct_fragment"]
        findings = (case.get("research_result") or {}).get("usable_findings") or []
        matched = [
            item for item in findings if marker in distinctive_fragments(item)
        ]
        self.assertEqual(len(matched), 1)
        fragments = distinctive_fragments(matched[0])
        self.assertIn("PercentCommittedBytesInUse", fragments)
        self.assertNotIn("AvailableMBytes", fragments)
        self.assertNotIn("FreePhysicalMemory", fragments)
        self.assertEqual(case["roles"]["A"], "complete")
        self.assertEqual(case["roles"]["B"], "similar_other_purpose")
        self.assertEqual(case["roles"]["C"], "legacy")
        self.assertEqual(case["roles"]["D"], "partial")


class JudgeAcceptImplementCaseTests(unittest.TestCase):
    def test_case_freezes_accept_finding_and_state(self):
        from research.llm_benchmarks.implementation_benchmark import expected_findings

        case = load_environment_case("implement_from_judge_accept_usage_percent")
        self.assertIsNotNone(case)
        self.assertTrue(case.get("check_registry"))
        self.assertTrue(case["judge"]["satisfies_request"])
        self.assertEqual(case["judge"]["missing"], [])
        usable = case["research_result"]["usable_findings"]
        self.assertEqual(usable[0]["evidence"]["sample"], ["48"])
        self.assertIn("TotalVisibleMemorySize", str(usable[0]["evidence"]["args"]))
        self.assertEqual(
            case["state"]["decisions"][1]["value"], "Windowsのメモリ使用率"
        )
        matched = expected_findings(case)
        self.assertEqual(len(matched), 1)
        self.assertIn("TotalVisibleMemorySize", distinctive_fragments(matched[0]))

    def test_using_adopted_script_is_ok(self):
        case = load_environment_case("implement_from_judge_accept_usage_percent")
        code = """
import subprocess
def get_memory_status():
    result = subprocess.run([
        'powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-WmiObject -Class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory,TotalVisibleMemorySize | ForEach-Object { [math]::Round(($_.FreePhysicalMemory / $_.TotalVisibleMemorySize) * 100) }'
    ], capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
        from research.llm_benchmarks.implementation_benchmark import expected_findings

        decision = classify_implementation(
            code=code,
            research_result=case["research_result"],
            expected_findings=expected_findings(case),
        )
        self.assertEqual(decision["class"], OK)
        self.assertTrue(decision["finding_adopted"])


if __name__ == "__main__":
    unittest.main()
