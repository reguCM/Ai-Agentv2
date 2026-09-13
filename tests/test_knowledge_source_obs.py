"""Knowledge Source Selection 観測層（行動変更なし）の単体テスト。"""

import os
import unittest

from tools.ai.state.knowledge_source import (
    assess_external_research_bundle,
    assess_known_coverage,
    build_proposal_observations,
    calibrate_proposals_with_results,
    knowledge_source_obs_enabled,
    observe_research_round,
    score_knowledge_sources,
)
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.task_state import TaskState


class KnowledgeSourceObsTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("AI_AGENT_KNOWLEDGE_SOURCE_OBS", None)

    def test_obs_disabled_by_default(self):
        os.environ.pop("AI_AGENT_KNOWLEDGE_SOURCE_OBS", None)
        self.assertFalse(knowledge_source_obs_enabled())

    def test_coverage_low_on_no_gain_fails(self):
        events = [
            {
                "id": "e1",
                "type": "verify_fail",
                "action": {"command": "powershell", "args": ["a"]},
                "result": {"ok": False, "error": "empty"},
                "metadata": {"round": 1},
            },
            {
                "id": "e2",
                "type": "verify_fail",
                "action": {"command": "powershell", "args": ["b"]},
                "result": {"ok": False, "error": "blank"},
                "metadata": {"round": 2},
            },
        ]
        state = TaskState(
            research_history=ResearchHistory.from_snapshot(events),
            open_questions=[
                {
                    "id": "q1",
                    "text": "CPU温度",
                    "status": "open",
                    "related_events": ["e1", "e2"],
                }
            ],
        )
        cov = assess_known_coverage(state)
        self.assertTrue(cov["no_gain"] or cov["same_error_class_continuing"])
        self.assertLess(cov["known_coverage"], 0.5)
        self.assertTrue(cov["not_for_decision"])

    def test_external_preferred_when_no_success(self):
        state = TaskState(
            research_history=ResearchHistory.from_snapshot(
                [
                    {
                        "id": "e1",
                        "type": "verify_fail",
                        "action": {"command": "powershell", "args": ["x"]},
                        "result": {"ok": False, "error": "empty"},
                        "metadata": {"round": 1},
                    },
                    {
                        "id": "e2",
                        "type": "verify_fail",
                        "action": {"command": "powershell", "args": ["y"]},
                        "result": {"ok": False, "error": "empty"},
                        "metadata": {"round": 2},
                    },
                ]
            ),
            open_questions=[
                {
                    "id": "q1",
                    "text": "温度",
                    "status": "open",
                    "related_events": ["e1", "e2"],
                }
            ],
        )
        scores = score_knowledge_sources(state, web_hit_count=3)
        self.assertFalse(scores["auto_switch"])
        self.assertIn(
            scores["preferred_source"],
            ("external_research", "experiment"),
        )

    def test_state_preferred_when_usable(self):
        state = TaskState(
            selected_findings=[{"summary": "ok", "finding_ref": "evt_1"}],
            research_history=ResearchHistory.from_snapshot(
                [
                    {
                        "id": "evt_1",
                        "type": "verify_ok",
                        "action": {"command": "powershell", "args": ["z"]},
                        "result": {"ok": True, "sample": ["42"]},
                        "metadata": {"round": 1},
                    }
                ]
            ),
        )
        scores = score_knowledge_sources(state)
        self.assertEqual(scores["preferred_source"], "state")

    def test_hit_evidence_axes(self):
        bundle = assess_external_research_bundle(
            [
                {
                    "title": "Get-CimInstance Win32_Processor",
                    "snippet": "PowerShell example on Windows",
                    "url": "https://learn.microsoft.com/windows",
                    "backend": "learn_microsoft",
                },
                {
                    "title": "Same mirrored page",
                    "snippet": "copy",
                    "url": "https://learn.microsoft.com/other",
                    "backend": "learn_microsoft",
                },
            ],
            open_questions=[{"text": "CPU temperature Win32"}],
        )
        self.assertGreaterEqual(bundle["hit_count"], 2)
        self.assertTrue(
            bundle["implementation_precedent_summary"]["exists"]
            or bundle["assessed_hits"][0]["source_reliability"]["category"]
            == "official_or_vendor_docs"
        )
        hit0 = bundle["assessed_hits"][0]
        self.assertIn("source_reliability", hit0)
        self.assertIn("evidence_relevance", hit0)
        self.assertIn("implementation_precedent", hit0)

    def test_proposal_calibration_links_result(self):
        coverage = {
            "has_usable_in_state": False,
            "no_gain": True,
            "known_coverage": 0.2,
        }
        scores = {
            "preferred_source": "external_research",
            "source_values": {"external_research": 0.8},
        }
        props = build_proposal_observations(
            [{"command": "powershell", "args": ["-Command", "Get-X"], "question": "q"}],
            coverage=coverage,
            source_scores=scores,
            external_bundle={"hit_count": 2, "implementation_precedent_summary": {"exists": True}},
        )
        self.assertEqual(len(props), 1)
        self.assertTrue(props[0]["not_for_decision"])
        self.assertIn("evidence_confidence", props[0])
        self.assertIn("expected_information_gain", props[0])
        calibrated = calibrate_proposals_with_results(
            props,
            [
                {
                    "confidence": "high",
                    "evidence": {
                        "command": "powershell",
                        "args": ["-Command", "Get-X"],
                    },
                }
            ],
            coverage_before=coverage,
            coverage_after={
                "has_usable_in_state": True,
                "no_gain": False,
                "known_coverage": 0.7,
            },
        )
        self.assertTrue(calibrated["proposals"][0]["actual_success"])
        self.assertTrue(calibrated["usable_gain_round"])

    def test_observe_round_bundle(self):
        state = TaskState()
        obs = observe_research_round(
            state,
            hits=[{"title": "t", "snippet": "s", "url": "https://example.com", "backend": "x"}],
            candidates=[{"command": "wmic", "args": ["cpu"]}],
            verified={"results": []},
            round_num=1,
        )
        self.assertTrue(obs["enabled"])
        self.assertFalse(obs["auto_switch"])
        self.assertFalse(obs["prompt_injected"])
        self.assertIn("knowledge_source_selection", obs)


if __name__ == "__main__":
    unittest.main()
