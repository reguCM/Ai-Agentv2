import unittest

from research.llm_benchmarks.research_followup_classify import inspect_research_followup
from tools.system.llm_failure_memory import load_environment_case

from research.llm_benchmarks.research_followup import build_materials


REJECTED = [
    {
        "command": "powershell",
        "args": [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-WmiObject -Class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory,TotalPhysicalMemory | ForEach-Object { [math]::Round(($_.FreePhysicalMemory / $_.TotalPhysicalMemory) * 100) }",
        ],
    }
]

INVENTORY = {"available_commands": ["powershell", "wmic"]}


class ResearchFollowupClassifyTests(unittest.TestCase):
    def test_case_builds_handoff_materials(self):
        case = load_environment_case("research_followup_after_verify_fail")
        self.assertIsNotNone(case)
        materials, filter_info = build_materials(case)
        self.assertEqual(
            materials.get("followup_questions"),
            ["total physical memory is still unconfirmed"],
        )
        self.assertEqual(len(materials.get("rejected_commands") or []), 1)
        self.assertTrue(materials.get("prior_failures"))
        self.assertEqual(filter_info["dropped_count"], 5)
        self.assertEqual(filter_info["kept_count"], 0)
        self.assertEqual(materials.get("search_results"), [])
        self.assertTrue(materials.get("empty_search"))
        self.assertTrue(materials.get("exploration_hints"))
        self.assertIn("wmic", "\n".join(materials.get("exploration_hints") or []))
        self.assertIn("not yet tried", "\n".join(materials.get("exploration_hints") or []).lower())
        self.assertIn("total physical memory", "\n".join(materials.get("search_keywords") or []))

    def test_empty_search_materials_include_restart_guidance_in_prompt(self):
        case = load_environment_case("research_followup_after_verify_fail")
        materials, _filter_info = build_materials(case)
        from tools.ai.llm.adapter import build_web_candidate_messages

        joined = "\n".join(
            item["content"]
            for item in build_web_candidate_messages(materials)
        )
        self.assertIn("exploration_hints", joined)
        self.assertIn("empty_search", joined)
        self.assertIn("start new exploration", joined.lower())
        self.assertIn("available_commands", joined)

    def test_case_freezes_captured_search_results_not_handwritten(self):
        case = load_environment_case("research_followup_after_verify_fail")
        hits = case.get("search_results") or []
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(case.get("search_results_captured_at"))
        joined = "\n".join(
            f"{item.get('title')} {item.get('snippet')}" for item in hits
        )
        self.assertNotIn("TotalVisibleMemorySize", joined)
        self.assertNotIn("example.com/memory-info", joined)

    def test_baseline_c_is_frozen(self):
        from pathlib import Path
        import json

        path = Path("research/llm_benchmarks/research_followup_baseline_c.json")
        baseline = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(baseline["trial_grades"], ["C", "C", "C"])
        self.assertEqual(baseline["observed_grades"], {"C": 3})
        self.assertFalse(baseline["pass"])

    def test_repeat_same_script_is_c(self):
        held = inspect_research_followup(
            {
                "candidates": [
                    {
                        "command": "powershell",
                        "args": [
                            "Get-WmiObject -Class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory,TotalPhysicalMemory | ForEach-Object { [math]::Round(($_.FreePhysicalMemory / $_.TotalPhysicalMemory) * 100) }"
                        ],
                    }
                ]
            },
            rejected_commands=REJECTED,
            inventory=INVENTORY,
            missing=["total physical memory is still unconfirmed"],
        )
        self.assertEqual(held["grade"], "C")
        self.assertTrue(held["repeat_count"] >= 1)
        self.assertFalse(held["ok"])

    def test_different_substantive_candidate_is_a(self):
        held = inspect_research_followup(
            {
                "candidates": [
                    {
                        "command": "powershell",
                        "args": [
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            "Get-WmiObject -Class Win32_OperatingSystem | Select-Object -Property FreePhysicalMemory,TotalVisibleMemorySize | ForEach-Object { [math]::Round(($_.FreePhysicalMemory / $_.TotalVisibleMemorySize) * 100) }",
                        ],
                        "question": "total physical memory is still unconfirmed",
                    }
                ]
            },
            rejected_commands=REJECTED,
            inventory=INVENTORY,
            missing=["total physical memory is still unconfirmed"],
        )
        self.assertEqual(held["grade"], "A")
        self.assertTrue(held["ok"])
        self.assertEqual(held["repeat_count"], 0)

    def test_different_but_vague_is_b(self):
        held = inspect_research_followup(
            {
                "candidates": [
                    {
                        "command": "powershell",
                        "args": [
                            "-NoProfile",
                            "-NonInteractive",
                            "-Command",
                            "Get-WmiObject Win32_OperatingSystem",
                        ],
                        "question": "total physical memory is still unconfirmed",
                    }
                ]
            },
            rejected_commands=REJECTED,
            inventory=INVENTORY,
            missing=["total physical memory is still unconfirmed"],
        )
        self.assertEqual(held["grade"], "B")
        self.assertFalse(held["ok"])

    def test_exploration_retry_needed_when_only_rejected_candidates(self):
        from tools.ai.tool_builder.web import exploration_retry_needed

        materials = {
            "empty_search": True,
            "rejected_commands": REJECTED,
            "prior_failures": [{"command": "powershell"}],
        }
        candidates = [
            {
                "command": "powershell",
                "args": REJECTED[0]["args"],
            }
        ]
        self.assertTrue(exploration_retry_needed(materials, candidates))
        self.assertFalse(
            exploration_retry_needed(
                materials,
                [
                    {
                        "command": "wmic",
                        "args": ["OS", "get", "TotalVisibleMemorySize"],
                    }
                ],
            )
        )

    def test_no_json_is_fail(self):
        held = inspect_research_followup(None, error="no_json", rejected_commands=REJECTED)
        self.assertEqual(held["grade"], "FAIL")
        self.assertFalse(held["ok"])


if __name__ == "__main__":
    unittest.main()
