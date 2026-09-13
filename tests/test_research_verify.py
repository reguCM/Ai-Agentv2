import unittest

from tools.ai.tool_builder.research_result import filter_rejected_candidates
from tools.system.tool_builder.research.verify import (
    candidate_is_allowed,
    normalize_candidate,
    run_candidate,
)


INVENTORY = {"available_commands": ["powershell", "wmic"]}

UNWRAPPED_OS = {
    "command": "powershell",
    "args": ["Get-CimInstance", "-Class", "Win32_OperatingSystem"],
}

FOURTH_FAILURE_SHAPE = {
    "command": "powershell",
    "args": [
        "Get-WmiObject",
        "-Class",
        "Win32_OperatingSystem",
        "|",
        "Select-Object",
        "-Property",
        "FreePhysicalMemory,TotalPhysicalMemory",
        "|",
        "ForEach-Object",
        "{",
        "[math]::Round(($_.FreePhysicalMemory",
        "/",
        "$_.TotalPhysicalMemory)",
        "*",
        "100)",
        "}",
    ],
}


class ResearchVerifierPipeTests(unittest.TestCase):
    def test_unwrapped_script_becomes_command_switch(self):
        normalized = normalize_candidate(UNWRAPPED_OS)
        self.assertEqual(normalized["command"], "powershell")
        self.assertEqual(
            normalized["args"][:3],
            ["-NoProfile", "-NonInteractive", "-Command"],
        )
        self.assertEqual(
            normalized["args"][3],
            "Get-CimInstance -Class Win32_OperatingSystem",
        )

    def test_already_wrapped_stays_canonical(self):
        wrapped = {
            "command": "powershell",
            "args": [
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance -Class Win32_OperatingSystem",
            ],
        }
        once = normalize_candidate(wrapped)
        twice = normalize_candidate(once)
        self.assertEqual(once["args"], twice["args"])
        self.assertEqual(once["args"][3], wrapped["args"][3])

    def test_command_switch_with_split_script_is_joined(self):
        normalized = normalize_candidate(
            {
                "command": "powershell",
                "args": [
                    "-Command",
                    "Get-WmiObject",
                    "-Class",
                    "Win32_OperatingSystem",
                ],
            }
        )
        self.assertEqual(
            normalized["args"],
            [
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-WmiObject -Class Win32_OperatingSystem",
            ],
        )

    def test_cmdlet_as_command_is_promoted_to_powershell(self):
        normalized = normalize_candidate(
            {
                "command": "Get-CimInstance",
                "args": ["-ClassName", "Win32_OperatingSystem"],
            }
        )
        self.assertEqual(normalized["command"], "powershell")
        self.assertEqual(normalized["args"][2], "-Command")
        self.assertIn("Get-CimInstance", normalized["args"][3])
        self.assertIn("Win32_OperatingSystem", normalized["args"][3])

    def test_fourth_failure_shape_is_allowed(self):
        allowed, errors, command, args = candidate_is_allowed(
            FOURTH_FAILURE_SHAPE, INVENTORY
        )
        self.assertTrue(allowed, errors)
        self.assertEqual(command, "powershell")
        self.assertEqual(args[2], "-Command")
        self.assertIn("Get-WmiObject", args[3])
        self.assertIn("Win32_OperatingSystem", args[3])

    def test_unwrapped_fetch_is_allowed(self):
        allowed, errors, command, args = candidate_is_allowed(
            UNWRAPPED_OS, INVENTORY
        )
        self.assertTrue(allowed, errors)
        self.assertEqual(args[:3], ["-NoProfile", "-NonInteractive", "-Command"])

    def test_unrelated_powershell_stays_rejected(self):
        allowed, errors, _command, _args = candidate_is_allowed(
            {"command": "powershell", "args": ["Get-Date"]},
            INVENTORY,
        )
        self.assertFalse(allowed)
        self.assertTrue(
            any("許可された取得用途ではありません" in item for item in errors)
        )

    def test_dangerous_command_stays_rejected(self):
        allowed, errors, _command, _args = candidate_is_allowed(
            {
                "command": "powershell",
                "args": ["Remove-Item", "-Recurse", "C:\\Windows"],
            },
            INVENTORY,
        )
        self.assertFalse(allowed)
        self.assertTrue(
            any("許可された取得用途ではありません" in item for item in errors)
        )

    def test_file_switch_is_not_rewritten_to_command(self):
        normalized = normalize_candidate(
            {
                "command": "powershell",
                "args": ["-File", "get-memory.ps1"],
            }
        )
        self.assertEqual(normalized["args"], ["-File", "get-memory.ps1"])
        allowed, _errors, _command, _args = candidate_is_allowed(
            normalized, INVENTORY
        )
        self.assertFalse(allowed)

    def test_rejected_filter_uses_canonical_form(self):
        rejected = [
            {
                "command": "powershell",
                "args": [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-CimInstance -Class Win32_OperatingSystem",
                ],
            }
        ]
        kept = filter_rejected_candidates([UNWRAPPED_OS], rejected)
        self.assertEqual(kept, [])
        other = filter_rejected_candidates(
            [
                {
                    "command": "powershell",
                    "args": ["Get-Counter", "\\Memory\\Available MBytes"],
                }
            ],
            rejected,
        )
        self.assertEqual(len(other), 1)
        self.assertEqual(other[0]["args"][2], "-Command")

    def test_unwrapped_os_candidate_runs(self):
        run = run_candidate(UNWRAPPED_OS, INVENTORY)
        self.assertTrue(run["ok"], run.get("error"))
        self.assertTrue(run["stdout"].strip())
        self.assertEqual(run["args"][2], "-Command")


if __name__ == "__main__":
    unittest.main()
