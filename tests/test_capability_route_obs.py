"""
CURSOR_VALIDATION: capability_route 観測（実行権限・Pipeline非接続）。
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.system import capability_route_obs as cro
from tools.system.execution_identity import PROJECT_AGENT


class CapabilityRouteObsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.obs_log = Path(self.tmp.name) / "cap.jsonl"
        self.id_log = Path(self.tmp.name) / "id.jsonl"
        self.env = mock.patch.dict(
            os.environ,
            {
                "AI_AGENT_CAPABILITY_ROUTE_LOG": str(self.obs_log),
                "AI_AGENT_EXECUTION_LOG": str(self.id_log),
            },
            clear=False,
        )
        self.env.start()
        self.registry = {
            "tools": [
                {"name": "search_web", "visibility": "agent"},
                {"name": "cpu_status", "visibility": "agent"},
                {"name": "create_tool_proposal", "visibility": "pipeline"},
            ]
        }

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_agent_continue_when_related_public(self):
        obs = cro.build_capability_route_observation(
            request="CPUの状態を教えて",
            registry=self.registry,
            related_tools=[{"name": "cpu_status", "score": 4}],
            agent_tools_tried=[],
        )
        self.assertEqual(obs["capability_route"]["route"], cro.ROUTE_AGENT_CONTINUE)
        self.assertTrue(obs["observation_only"])
        self.assertTrue(obs["does_not_grant_tool_execution"])
        self.assertTrue(obs["does_not_start_pipeline"])
        self.assertEqual(obs["execution_actor"], PROJECT_AGENT)

    def test_needs_new_tool_hint_without_related(self):
        obs = cro.build_capability_route_observation(
            request="新しいToolを作ってメモリ使用率を取得してください",
            registry=self.registry,
            related_tools=[],
            agent_tools_tried=[],
        )
        self.assertEqual(obs["capability_route"]["route"], cro.ROUTE_NEEDS_NEW_TOOL)

    def test_web_judgment_separate_from_execution(self):
        obs = cro.build_capability_route_observation(
            request="Webで最新情報を検索して比較してください",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 2}],
            agent_tools_tried=[],
        )
        web = obs["web_search"]
        self.assertTrue(web["judgment"]["judged_appropriate"])
        self.assertTrue(web["judgment"]["recognized_as_candidate"])
        self.assertFalse(web["execution"]["called"])
        self.assertEqual(web["execution"]["call_count"], 0)

        trial = cro.build_tool_trial(
            "search_web",
            {"query": "x"},
            {"query": "x", "hits": [], "error": None},
        )
        obs2 = cro.build_capability_route_observation(
            request="Webで最新情報を検索して比較してください",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 2}],
            agent_tools_tried=[trial],
        )
        self.assertTrue(obs2["web_search"]["execution"]["called"])
        self.assertEqual(obs2["web_search"]["execution"]["outcomes"], ["empty_hits"])
        # 判断フィールドは実行で上書きしない
        self.assertTrue(obs2["web_search"]["judgment"]["judged_appropriate"])

    def test_search_web_outcomes(self):
        self.assertEqual(
            cro.classify_search_web_outcome({"hits": [{"url": "u"}], "error": None}),
            "hits",
        )
        self.assertEqual(
            cro.classify_search_web_outcome({"hits": [], "error": None}),
            "empty_hits",
        )
        self.assertEqual(
            cro.classify_search_web_outcome(
                {"blocked_by_agent_tool_gate": True, "ok": False}
            ),
            "blocked",
        )
        self.assertEqual(
            cro.classify_search_web_outcome({"hits": [], "error": "boom"}),
            "error",
        )

    def test_record_writes_obs_and_identity(self):
        obs = cro.build_capability_route_observation(
            request="調べて",
            registry=self.registry,
            related_tools=[],
            agent_tools_tried=[],
            observation_id="caproute-test",
        )
        cro.record_capability_route_observation(obs)
        rows = [
            json.loads(line)
            for line in self.obs_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows[0]["observation_id"], "caproute-test")
        id_rows = [
            json.loads(line)
            for line in self.id_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(id_rows[0]["event"], "capability_route_observed")
        self.assertEqual(id_rows[0]["execution_actor"], PROJECT_AGENT)

    def test_module_does_not_start_pipeline_or_bypass_gate(self):
        source = Path(cro.__file__).read_text(encoding="utf-8")
        self.assertNotIn("research_implement", source)
        self.assertNotIn("register_tool", source)
        self.assertNotIn("bypass_tool_gate", source)
        self.assertNotIn("AI_AGENT_TOOL_GATE", source)
        self.assertNotIn("decide_execution_gate", source)
        self.assertNotIn("from tools.ai.state", source)

    def test_stage2_empty_hits_answer_failure_pattern(self):
        trial = cro.build_tool_trial(
            "search_web",
            {"query": "q"},
            {"hits": [], "error": None},
        )
        obs = cro.build_capability_route_observation(
            request="Webで最新情報を検索してください",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 2}],
            agent_tools_tried=[trial],
            observation_id="caproute-s2a",
        )
        compare = cro.build_capability_outcome_compare(
            capability_observation=obs,
            final_answer_content="",
            observation_id="caproute-s2a",
        )
        self.assertEqual(compare["kind"], "capability_outcome_compare")
        self.assertEqual(compare["stage"], 2)
        self.assertIsNone(compare["misjudgment_classification"])
        self.assertTrue(compare["not_stage3_misjudgment"])
        self.assertEqual(
            compare["compare_summary"]["web_pattern"],
            "web_judged_called_empty_hits_answer_failure_candidate",
        )
        self.assertEqual(
            compare["chain"]["final_answer"]["outcome_proxy"],
            cro.OUTCOME_FAILURE_CANDIDATE,
        )

    def test_stage2_hits_answer_success_candidate_pattern(self):
        trial = cro.build_tool_trial(
            "search_web",
            {"query": "q"},
            {"hits": [{"title": "t", "url": "https://example.com"}], "error": None},
        )
        obs = cro.build_capability_route_observation(
            request="Webで調べてください",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 2}],
            agent_tools_tried=[trial],
            observation_id="caproute-s2b",
        )
        compare = cro.build_capability_outcome_compare(
            capability_observation=obs,
            final_answer_content="根拠URLは https://example.com です。",
        )
        self.assertEqual(
            compare["compare_summary"]["web_pattern"],
            "web_judged_called_hits_answer_success_candidate",
        )

    def test_stage2_record_shares_observation_id(self):
        obs = cro.build_capability_route_observation(
            request="検索して",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 1}],
            agent_tools_tried=[],
            observation_id="caproute-link",
        )
        cro.record_capability_route_observation(obs)
        compare = cro.build_capability_outcome_compare(
            capability_observation=obs,
            final_answer_content="確認できなかった",
            observation_id="caproute-link",
        )
        cro.record_capability_outcome_compare(compare)
        rows = [
            json.loads(line)
            for line in self.obs_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows[0]["kind"], "capability_route_observation")
        self.assertEqual(rows[1]["kind"], "capability_outcome_compare")
        self.assertEqual(rows[0]["observation_id"], rows[1]["observation_id"])
        id_events = [
            json.loads(line)["event"]
            for line in self.id_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(
            id_events,
            ["capability_route_observed", "capability_outcome_compared"],
        )

    def test_pre_web_candidate_linked_and_distinct_from_web_results(self):
        pre = cro.build_pre_web_answer_candidate(
            request="最新のPythonリリースを調べて",
            content="手元の知識では 3.12 系が現行だが、未確認。",
            observation_id="caproute-preweb",
        )
        self.assertEqual(pre["kind"], "pre_web_answer_candidate")
        self.assertTrue(pre["does_not_authorize_web_search"])
        self.assertTrue(pre["not_web_usefulness_judgment"])
        self.assertTrue(
            (pre["pre_web_answer_candidate"] or {}).get("web_search_not_used")
        )
        cro.record_pre_web_answer_candidate(pre)

        trial = cro.build_tool_trial(
            "search_web",
            {"query": "python release"},
            {
                "query": "python release",
                "hits": [
                    {
                        "title": "Python 3.13",
                        "url": "https://www.python.org/downloads/",
                        "snippet": "Download the latest",
                    }
                ],
                "error": None,
            },
        )
        self.assertEqual(trial["hit_digest"][0]["title"], "Python 3.13")
        obs = cro.build_capability_route_observation(
            request="最新のPythonリリースを調べて",
            registry=self.registry,
            related_tools=[{"name": "search_web", "score": 2}],
            agent_tools_tried=[trial],
            observation_id="caproute-preweb",
        )
        cro.record_capability_route_observation(obs)
        results = cro.build_web_search_results_digest([trial])
        self.assertTrue(results["not_final_answer"])
        self.assertEqual(results["call_count"], 1)
        compare = cro.build_capability_outcome_compare(
            capability_observation=obs,
            final_answer_content="公式によると 3.13 です。",
            observation_id="caproute-preweb",
            pre_web_answer_candidate=pre,
            web_search_results=results,
        )
        cro.record_capability_outcome_compare(compare)
        chain = compare["chain"]
        self.assertIn("pre_web_answer_candidate", chain)
        self.assertIn("web_judgment", chain)
        self.assertIn("web_execution", chain)
        self.assertIn("web_search_results", chain)
        self.assertIn("final_answer", chain)
        self.assertNotEqual(
            chain["pre_web_answer_candidate"]["content"],
            chain["final_answer"].get("status"),
        )
        self.assertEqual(
            chain["web_search_results"]["calls"][0]["hit_digest"][0]["url"],
            "https://www.python.org/downloads/",
        )
        self.assertEqual(
            chain["final_answer"]["status"], cro.ANSWER_PRESENT
        )
        self.assertIsNone(compare["misjudgment_classification"])
        self.assertTrue(compare["not_web_usefulness_judgment"])
        self.assertNotIn("web_was_beneficial", compare)
        self.assertNotIn("web_needed_truth", compare)

        rows = [
            json.loads(line)
            for line in self.obs_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        kinds = [r["kind"] for r in rows]
        self.assertEqual(
            kinds,
            [
                "pre_web_answer_candidate",
                "capability_route_observation",
                "capability_outcome_compare",
            ],
        )
        self.assertTrue(all(r["observation_id"] == "caproute-preweb" for r in rows))
        id_events = [
            json.loads(line)["event"]
            for line in self.id_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(
            id_events,
            [
                "pre_web_answer_candidate_observed",
                "capability_route_observed",
                "capability_outcome_compared",
            ],
        )

    def test_pre_web_recorded_when_web_not_called(self):
        pre = cro.build_pre_web_answer_candidate(
            request="CPUの状態を教えて",
            content="ローカルToolで確認する想定です。",
            observation_id="caproute-noweb",
        )
        obs = cro.build_capability_route_observation(
            request="CPUの状態を教えて",
            registry=self.registry,
            related_tools=[{"name": "cpu_status", "score": 4}],
            agent_tools_tried=[],
            observation_id="caproute-noweb",
        )
        compare = cro.build_capability_outcome_compare(
            capability_observation=obs,
            final_answer_content="CPUは正常です。",
            observation_id="caproute-noweb",
            pre_web_answer_candidate=pre,
        )
        self.assertFalse(compare["chain"]["web_execution"]["called"])
        self.assertIsNotNone(compare["chain"]["pre_web_answer_candidate"])
        self.assertFalse(compare["chain"]["web_search_results"]["called"])


if __name__ == "__main__":
    unittest.main()
