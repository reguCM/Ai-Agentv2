import copy
import unittest

from tools.ai.llm.adapter import dumps_json
from tools.ai.tool_builder.research_judge import (
    compact_unresolved_finding,
    create_research_judgment,
)
from tools.system.config import get_llm_profile

CPU_TEMP_UNRESOLVED = {
    "kind": "output",
    "question": "total physical memory is still unconfirmed",
    "finding": (
        "実環境で確認できなかった。Select-Object : プロパティ \"Temperature\" が見つかりません。\n"
        "発生場所 行:1 文字:46\n+ ... ClassName Win32_Processor | Select-Object -ExpandProperty Temperature\n"
        "+                                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
        "    + CategoryInfo          : InvalidArgument: (Win32_Processor...iceID = \"CPU0\"):PSObject) [Select-Object]、PSArgument \n"
        "   Exception\n"
        "    + FullyQualifiedErrorId : ExpandPropertyNotFound,Microsoft.PowerShell.Commands.SelectObjectCommand"
    ),
    "evidence": {
        "command": "powershell",
        "args": [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance -ClassName Win32_Processor | Select-Object -ExpandProperty Temperature",
        ],
        "returncode": 1,
        "sample": [],
        "stderr": "Select-Object : プロパティ \"Temperature\" が見つかりません。\n" + "x" * 400,
        "error": "Select-Object : プロパティ \"Temperature\" が見つかりません。\n" + "x" * 400,
        "output_key": "status",
    },
    "confidence": "low",
    "source": "web",
}

LOCAL_UNRESOLVED = {
    "kind": "output",
    "question": "used memory is still unconfirmed",
    "finding": "Web調査後も取得方法を実環境で確認できなかった",
    "evidence": {
        "platform": "Windows",
        "available_modules": ["platform"],
        "missing_modules": ["psutil"],
        "available_commands": ["wmic", "powershell"],
    },
    "confidence": "low",
    "source": "local",
}


class CompactUnresolvedFindingTests(unittest.TestCase):
    def test_short_texts_unchanged(self):
        item = {
            "question": "q" * 120,
            "finding": "f" * 200,
            "evidence": {
                "command": "powershell",
                "args": ["-Command", "ok"],
                "sample": ["1"],
                "error": "e" * 120,
            },
        }
        compact = compact_unresolved_finding(item)
        self.assertEqual(compact["question"], item["question"])
        self.assertEqual(compact["finding"], item["finding"])
        self.assertEqual(compact["evidence"]["error"], item["evidence"]["error"])
        self.assertNotIn("stderr", compact["evidence"])

    def test_long_texts_truncated(self):
        compact = compact_unresolved_finding(CPU_TEMP_UNRESOLVED)
        self.assertLessEqual(len(compact["finding"]), 201)
        self.assertLessEqual(len(compact["question"]), 121)
        self.assertLessEqual(len(compact["evidence"]["error"]), 121)
        self.assertTrue(compact["finding"].endswith("…"))
        self.assertTrue(compact["evidence"]["error"].endswith("…"))

    def test_duplicate_stderr_omitted(self):
        compact = compact_unresolved_finding(CPU_TEMP_UNRESOLVED)
        self.assertIn("error", compact["evidence"])
        self.assertNotIn("stderr", compact["evidence"])

    def test_keeps_command_args_sample(self):
        compact = compact_unresolved_finding(CPU_TEMP_UNRESOLVED)
        self.assertEqual(compact["evidence"]["command"], "powershell")
        self.assertEqual(
            compact["evidence"]["args"],
            CPU_TEMP_UNRESOLVED["evidence"]["args"],
        )
        self.assertEqual(compact["evidence"]["sample"], [])

    def test_sample_capped_to_three_lines(self):
        item = {
            "finding": "ok",
            "evidence": {"sample": ["1", "2", "3", "4", "5"]},
        }
        compact = compact_unresolved_finding(item)
        self.assertEqual(compact["evidence"]["sample"], ["1", "2", "3"])

    def test_local_inventory_evidence_preserved(self):
        compact = compact_unresolved_finding(LOCAL_UNRESOLVED)
        self.assertEqual(compact["evidence"]["platform"], "Windows")
        self.assertEqual(compact["evidence"]["available_commands"], ["wmic", "powershell"])

    def test_create_research_judgment_compacts_materials_only(self):
        research = {
            "usable_findings": [],
            "insufficient_findings": [],
            "unresolved": [copy.deepcopy(CPU_TEMP_UNRESOLVED)],
        }
        original = copy.deepcopy(research)
        materials = create_research_judgment("req", {"output": ["status"]}, research)
        self.assertEqual(research, original)
        self.assertLess(
            len(dumps_json(materials["unresolved"], get_llm_profile())),
            len(dumps_json(research["unresolved"], get_llm_profile())),
        )
        self.assertNotIn("stderr", materials["unresolved"][0]["evidence"])

    def test_verify_retry_phrase_survives_in_finding(self):
        item = {
            "question": "q",
            "finding": "実環境で確認できなかった。0 で除算しようとしました。" + ("x" * 300),
            "evidence": {
                "command": "powershell",
                "args": ["-Command", "bad"],
                "sample": [],
                "error": "0 で除算しようとしました。" + ("y" * 300),
                "stderr": "0 で除算しようとしました。" + ("y" * 300),
            },
        }
        materials = create_research_judgment(
            "req", {"output": ["status"]}, {"unresolved": [item]}
        )
        self.assertIn("0 で除算", materials["unresolved"][0]["finding"])


if __name__ == "__main__":
    unittest.main()
