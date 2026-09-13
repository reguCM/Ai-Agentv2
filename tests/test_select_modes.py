import unittest

from tools.system.llm_failure_memory import load_environment_case
from tools.system.tool_builder.implementation_classify import (
    FINDING_NOT_USED,
    OK,
    UNNECESSARY_FINDING,
    classify_implementation,
    distinctive_fragments,
    fragment_in_code,
    uses_finding,
)
from tools.system.tool_builder.score import score_implementation


FINDING_USAGE = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse",
        ],
        "sample": ["43.2"],
    }
}
FINDING_AVAILABLE = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes",
        ],
        "sample": ["8192"],
    }
}
FINDING_TOTAL = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize",
        ],
        "sample": ["16384000"],
    }
}
FINDING_USED = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select CommittedBytes",
        ],
        "sample": ["7516192768"],
    }
}
FINDING_FREE = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-Command",
            "Get-CimInstance -Class Win32_OperatingSystem | Select FreePhysicalMemory",
        ],
        "sample": ["9342000"],
    }
}

CODE_USAGE = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
CODE_AVAILABLE = """
import subprocess
def get_memory_status():
    result = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes'],
        capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""
CODE_USAGE_AND_AVAILABLE = """
import subprocess
def get_memory_status():
    usage = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    available = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes'],
        capture_output=True, text=True)
    return {'usage': usage.stdout.strip(), 'available': available.stdout.strip()}
"""
CODE_USAGE_AVAILABLE_FREE = """
import subprocess
def get_memory_status():
    usage = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'],
        capture_output=True, text=True)
    available = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select AvailableMBytes'],
        capture_output=True, text=True)
    free = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select FreePhysicalMemory'],
        capture_output=True, text=True)
    return {'usage': usage.stdout.strip(), 'available': available.stdout.strip(), 'free': free.stdout.strip()}
"""
CODE_TOTAL_AND_USED = """
import subprocess
def get_memory_status():
    total = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_OperatingSystem | Select TotalVisibleMemorySize'],
        capture_output=True, text=True)
    used = subprocess.run(['powershell', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select CommittedBytes'],
        capture_output=True, text=True)
    return {'status': total.stdout.strip() + used.stdout.strip()}
"""


def classified(code, expected, research):
    return classify_implementation(
        code=code,
        research_result=research,
        expected_findings=expected,
    )


class SelectModeTests(unittest.TestCase):
    def test_committed_bytes_is_not_substring_of_percent(self):
        self.assertTrue(fragment_in_code(CODE_USAGE, "PercentCommittedBytesInUse"))
        self.assertFalse(fragment_in_code(CODE_USAGE, "CommittedBytes"))
        self.assertFalse(uses_finding(CODE_USAGE, FINDING_USED))

    def test_single_select_extra_is_unnecessary(self):
        research = {
            "usable_findings": [
                FINDING_AVAILABLE,
                FINDING_FREE,
                FINDING_USAGE,
            ]
        }
        expected = [FINDING_USAGE]
        self.assertEqual(
            classified(CODE_USAGE, expected, research)["class"], OK
        )
        extra = classified(CODE_USAGE_AND_AVAILABLE, expected, research)
        self.assertEqual(extra["class"], UNNECESSARY_FINDING)
        scored = score_implementation(classified=extra)
        self.assertTrue(scored["pass"])
        self.assertEqual(scored["score"], 98)

    def test_multi_select_requires_both(self):
        research = {
            "usable_findings": [
                FINDING_FREE,
                FINDING_USAGE,
                FINDING_AVAILABLE,
            ]
        }
        expected = [FINDING_USAGE, FINDING_AVAILABLE]
        only_a = classified(CODE_USAGE, expected, research)
        self.assertEqual(only_a["class"], FINDING_NOT_USED)
        self.assertFalse(only_a["finding_adopted"])
        self.assertTrue(only_a["missing"])
        both = classified(CODE_USAGE_AND_AVAILABLE, expected, research)
        self.assertEqual(both["class"], OK)
        scored_both = score_implementation(classified=both)
        self.assertTrue(scored_both["pass"])
        self.assertEqual(scored_both["score"], 100)
        scored_a = score_implementation(classified=only_a)
        self.assertFalse(scored_a["pass"])
        extra = classified(CODE_USAGE_AVAILABLE_FREE, expected, research)
        self.assertEqual(extra["class"], UNNECESSARY_FINDING)

    def test_combine_rejects_shortcut_percent(self):
        research = {
            "usable_findings": [
                FINDING_AVAILABLE,
                FINDING_USAGE,
                FINDING_TOTAL,
                FINDING_USED,
            ]
        }
        expected = [FINDING_TOTAL, FINDING_USED]
        shortcut = classified(CODE_USAGE, expected, research)
        self.assertEqual(shortcut["class"], FINDING_NOT_USED)
        combined = classified(CODE_TOTAL_AND_USED, expected, research)
        self.assertEqual(combined["class"], OK)
        self.assertTrue(score_implementation(classified=combined)["pass"])

    def test_case_files_resolve_expected_fragments(self):
        from research.llm_benchmarks.implementation_benchmark import expected_findings

        single = load_environment_case("implement_single_select_memory_usage")
        multi = load_environment_case("implement_multi_select_usage_and_available")
        combine = load_environment_case("implement_combine_total_and_used_to_usage")
        single_ids = [distinctive_fragments(item) for item in expected_findings(single)]
        multi_ids = [distinctive_fragments(item) for item in expected_findings(multi)]
        combine_ids = [distinctive_fragments(item) for item in expected_findings(combine)]
        self.assertEqual(len(single_ids), 1)
        self.assertIn("PercentCommittedBytesInUse", single_ids[0])
        self.assertEqual(len(multi_ids), 2)
        self.assertTrue(
            any("PercentCommittedBytesInUse" in item for item in multi_ids)
        )
        self.assertTrue(any("AvailableMBytes" in item for item in multi_ids))
        self.assertEqual(len(combine_ids), 2)
        self.assertTrue(any("TotalVisibleMemorySize" in item for item in combine_ids))
        self.assertTrue(any("CommittedBytes" in item for item in combine_ids))
        self.assertFalse(
            any("PercentCommittedBytesInUse" in item for item in combine_ids)
        )


if __name__ == "__main__":
    unittest.main()
