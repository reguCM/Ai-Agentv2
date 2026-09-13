"""get_cpu_status — deterministic contract + local CIM real observation."""
from __future__ import annotations

import json
import platform
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from tools.system.cpu.get_cpu_status import UNKNOWN, get_cpu_status


class GetCpuStatusDeterministicTests(unittest.TestCase):
    def test_success_shape(self):
        payload = {
            "Name": "Test CPU",
            "NumberOfCores": 6,
            "NumberOfLogicalProcessors": 12,
            "MaxClockSpeed": 2500,
            "CurrentClockSpeed": 2400,
            "Architecture": 9,
            "LoadPercentage": 42,
        }
        with mock.patch("platform.system", return_value="Windows"), mock.patch(
            "tools.system.cpu.get_cpu_status.subprocess.run",
            return_value=mock.Mock(returncode=0, stdout=json.dumps(payload), stderr=""),
        ):
            out = get_cpu_status()
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["model"], "Test CPU")
        self.assertEqual(out["physical_cores"], 6)
        self.assertEqual(out["logical_processors"], 12)
        self.assertEqual(out["load_percentage"], 42)
        self.assertEqual(out["max_clock_mhz"], 2500)
        self.assertEqual(out["current_clock_mhz"], 2400)
        self.assertEqual(out["architecture"], 9)
        self.assertEqual(out["observation_source"], "real")
        self.assertEqual(out["source"], "win32_processor_cim")

    def test_non_windows_unavailable(self):
        with mock.patch("platform.system", return_value="Linux"):
            out = get_cpu_status()
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "unavailable")
        self.assertEqual(out["model"], UNKNOWN)

    def test_cim_failure_unknown_fields(self):
        with mock.patch("platform.system", return_value="Windows"), mock.patch(
            "tools.system.cpu.get_cpu_status.subprocess.run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="fail"),
        ):
            out = get_cpu_status()
        self.assertFalse(out["ok"])
        self.assertEqual(out["load_percentage"], UNKNOWN)

    def test_legacy_cpu_status_unchanged(self):
        import tools.system.cpu.cpu_status as legacy_cpu

        legacy_src = Path(legacy_cpu.__file__).read_text(encoding="utf-8")
        self.assertIn("LoadPercentage", legacy_src)
        self.assertNotIn("get_cpu_status", legacy_src)


class GetCpuStatusRealObservationTests(unittest.TestCase):
    @unittest.skipUnless(platform.system().lower() == "windows", "Windows CIM only")
    def test_matches_independent_cim_probe(self):
        ps = (
            "Get-CimInstance Win32_Processor | "
            "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,LoadPercentage | "
            "ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        indep = json.loads(proc.stdout.strip())
        if isinstance(indep, list):
            indep = indep[0]

        out = get_cpu_status()
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["model"], indep.get("Name"))
        self.assertEqual(out["physical_cores"], int(indep.get("NumberOfCores")))
        self.assertEqual(out["logical_processors"], int(indep.get("NumberOfLogicalProcessors")))
        indep_load = int(indep.get("LoadPercentage"))
        self.assertIsInstance(out["load_percentage"], int)
        self.assertLessEqual(abs(out["load_percentage"] - indep_load), 15)


class GetCpuStatusRegistryTests(unittest.TestCase):
    def test_registry_entry_agent_visible(self):
        registry = json.loads(
            (Path(__file__).resolve().parents[1] / "registry" / "tools.json").read_text(
                encoding="utf-8"
            )
        )
        by_name = {t["name"]: t for t in registry["tools"]}
        entry = by_name["get_cpu_status"]
        self.assertEqual(entry["visibility"], "agent")
        self.assertEqual(entry["observation_source"], "real")
        self.assertEqual(entry["function"], "get_cpu_status")


if __name__ == "__main__":
    unittest.main()
