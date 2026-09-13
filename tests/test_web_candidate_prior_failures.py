import copy
import unittest

from tools.ai.tool_builder.research_result import compact_prior_failures
from tools.ai.tool_builder.web import (
    compact_prior_failures_for_candidate,
    web_research,
)


OVERLAP_FAILURE = {
    "question": "CPU温度の具体的な取得方法が確認できていない",
    "command": "powershell",
    "args": [
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-WmiObject Win32_Processor",
    ],
    "error": "",
    "finding": "実環境で取得できた。command=powershell。戻り値サンプルあり",
}

OVERLAP_WITH_ERROR = {
    "question": "output 'status' の取得方法",
    "command": "powershell",
    "args": [
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-WmiObject -Class Win32_Processor | Select-Object -ExpandProperty Temperature",
    ],
    "error": 'Select-Object : プロパティ "Temperature" が見つかりません。',
    "finding": "実環境で確認できなかった。",
}

UNIQUE_FAILURE = {
    "question": "別経路の確認",
    "command": "wmic",
    "args": ["cpu", "get", "temperature"],
    "error": "No Instance(s) Available.",
    "finding": "wmic では温度を取得できなかった",
}

REJECTED = [
    {
        "command": OVERLAP_FAILURE["command"],
        "args": list(OVERLAP_FAILURE["args"]),
    },
    {
        "command": OVERLAP_WITH_ERROR["command"],
        "args": list(OVERLAP_WITH_ERROR["args"]),
    },
]


class WebCandidatePriorFailuresTests(unittest.TestCase):
    def test_overlap_omits_only_command_and_args(self):
        compacted = compact_prior_failures_for_candidate(
            [OVERLAP_FAILURE], REJECTED[:1]
        )
        self.assertEqual(len(compacted), 1)
        self.assertNotIn("command", compacted[0])
        self.assertNotIn("args", compacted[0])
        self.assertEqual(compacted[0]["question"], OVERLAP_FAILURE["question"])
        self.assertEqual(compacted[0]["finding"], OVERLAP_FAILURE["finding"])

    def test_empty_error_field_omitted(self):
        compacted = compact_prior_failures_for_candidate(
            [OVERLAP_FAILURE], REJECTED[:1]
        )
        self.assertNotIn("error", compacted[0])

    def test_nonempty_error_kept(self):
        compacted = compact_prior_failures_for_candidate(
            [OVERLAP_WITH_ERROR], REJECTED[1:]
        )
        self.assertEqual(compacted[0]["error"], OVERLAP_WITH_ERROR["error"])
        self.assertNotIn("command", compacted[0])
        self.assertNotIn("args", compacted[0])

    def test_non_overlap_keeps_command_args(self):
        compacted = compact_prior_failures_for_candidate(
            [UNIQUE_FAILURE], REJECTED
        )
        self.assertEqual(compacted[0]["command"], UNIQUE_FAILURE["command"])
        self.assertEqual(compacted[0]["args"], UNIQUE_FAILURE["args"])
        self.assertEqual(compacted[0]["question"], UNIQUE_FAILURE["question"])
        self.assertEqual(compacted[0]["finding"], UNIQUE_FAILURE["finding"])
        self.assertEqual(compacted[0]["error"], UNIQUE_FAILURE["error"])

    def test_rejected_commands_unchanged_in_web_research(self):
        rejected = copy.deepcopy(REJECTED)
        materials = web_research(
            prior_failures=[OVERLAP_FAILURE, UNIQUE_FAILURE],
            rejected_commands=rejected,
            inventory={"available_commands": ["powershell", "wmic"]},
        )
        self.assertEqual(materials["rejected_commands"], rejected)
        self.assertEqual(
            materials["rejected_commands"][0]["command"], "powershell"
        )
        self.assertEqual(
            materials["rejected_commands"][0]["args"], OVERLAP_FAILURE["args"]
        )

    def test_web_research_applies_candidate_compact(self):
        materials = web_research(
            prior_failures=[OVERLAP_FAILURE, OVERLAP_WITH_ERROR, UNIQUE_FAILURE],
            rejected_commands=REJECTED,
            inventory={"available_commands": ["powershell", "wmic"]},
        )
        priors = materials["prior_failures"]
        self.assertEqual(len(priors), 3)
        self.assertNotIn("command", priors[0])
        self.assertNotIn("args", priors[0])
        self.assertNotIn("error", priors[0])
        self.assertEqual(priors[0]["finding"], OVERLAP_FAILURE["finding"])
        self.assertNotIn("command", priors[1])
        self.assertIn("error", priors[1])
        self.assertEqual(priors[2]["command"], "wmic")

    def test_source_prior_failures_not_mutated(self):
        prior = copy.deepcopy([OVERLAP_FAILURE, UNIQUE_FAILURE])
        original = copy.deepcopy(prior)
        compact_prior_failures_for_candidate(prior, REJECTED)
        self.assertEqual(prior, original)

    def test_compact_prior_failures_unchanged(self):
        research = {
            "unresolved": [
                {
                    "question": OVERLAP_WITH_ERROR["question"],
                    "finding": OVERLAP_WITH_ERROR["finding"],
                    "evidence": {
                        "command": OVERLAP_WITH_ERROR["command"],
                        "args": OVERLAP_WITH_ERROR["args"],
                        "error": OVERLAP_WITH_ERROR["error"],
                    },
                }
            ],
            "insufficient_findings": [],
        }
        prior = compact_prior_failures(research)
        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0]["command"], OVERLAP_WITH_ERROR["command"])
        self.assertEqual(prior[0]["args"], OVERLAP_WITH_ERROR["args"])
        self.assertIn("error", prior[0])
        self.assertIn("finding", prior[0])


if __name__ == "__main__":
    unittest.main()
