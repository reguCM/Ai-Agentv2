import os
import unittest
from unittest.mock import patch

from tools.ai.llm.adapter import build_research_judge_messages, build_web_candidate_messages
from tools.ai.llm.context_allocation import (
    BUILDER_JUDGE,
    BUILDER_WEB,
    RESERVED_HEADROOM_CHARS,
    allocate_judge_materials,
    allocate_web_candidate_materials,
    compact_state_for_prompt,
    effective_budget_chars,
    finalize_context_budget_shadow,
    headroom_gate_ok,
    init_context_budget_shadow,
    measure_prompt_sections,
    prepare_context_allocation_call,
    prior_failures_from_retriever,
)
from tools.ai.llm.context_budget import (
    check_context_budget,
    effective_prompt_budget_chars,
)
from tools.ai.state.research_history import ResearchHistory
from tools.ai.state.task_state import TaskState


class Phase4ContextAllocationTests(unittest.TestCase):
    def setUp(self):
        # 既定は live ON。テストごとに明示する。
        os.environ.pop("AI_AGENT_CONTEXT_ALLOC_LIVE", None)
        os.environ["AI_AGENT_CONTEXT_ALLOC_SHADOW"] = "1"

    def test_live_enabled_by_default(self):
        from tools.ai.llm.context_allocation import context_alloc_live_enabled

        os.environ.pop("AI_AGENT_CONTEXT_ALLOC_LIVE", None)
        self.assertTrue(context_alloc_live_enabled())
        with patch.dict(os.environ, {"AI_AGENT_CONTEXT_ALLOC_LIVE": "0"}, clear=False):
            self.assertFalse(context_alloc_live_enabled())
        with patch.dict(os.environ, {"AI_AGENT_CONTEXT_ALLOC_LIVE": "1"}, clear=False):
            self.assertTrue(context_alloc_live_enabled())

    def test_effective_budget_reserves_headroom(self):
        profile = {"context_limit": 4096, "num_predict": 2048}
        total = (4096 - 2048 - 128) * 4
        self.assertEqual(effective_prompt_budget_chars(profile), total - RESERVED_HEADROOM_CHARS)
        self.assertEqual(effective_budget_chars(profile), total - RESERVED_HEADROOM_CHARS)

    def test_check_context_budget_with_headroom(self):
        profile = {"context_limit": 4096, "num_predict": 2048}
        budget = effective_prompt_budget_chars(profile)
        ok_messages = [{"role": "user", "content": "x" * budget}]
        self.assertIsNone(
            check_context_budget(ok_messages, profile, reserve_headroom=True)
        )
        over_messages = [{"role": "user", "content": "x" * (budget + 1)}]
        detail = check_context_budget(over_messages, profile, reserve_headroom=True)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["headroom_chars"], RESERVED_HEADROOM_CHARS)

    def test_compact_state_drops_unresolved_when_open_questions_exist(self):
        state = TaskState(
            task="CPU温度",
            open_questions=[{"id": "q1", "text": "温度取得", "status": "open"}],
            unresolved=[{"question": "dup", "finding": "event:evt_1"}],
        )
        payload = compact_state_for_prompt(state)
        self.assertTrue(payload.get("open_questions"))
        self.assertNotIn("unresolved", payload)

    def test_prior_failures_from_retriever_uses_history_not_full_stderr(self):
        history = ResearchHistory.from_snapshot(
            [
                {
                    "id": "evt_1",
                    "type": "verify_fail",
                    "action": {"command": "powershell", "args": ["-Command", "x"]},
                    "result": {
                        "ok": False,
                        "stderr": "E" * 500,
                        "error": "property_not_found",
                    },
                }
            ]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "CPU温度",
                    "status": "open",
                    "related_events": ["evt_1"],
                }
            ],
            research_history=history,
        )
        failures, events = prior_failures_from_retriever(state, limit=2)
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(events), 1)
        self.assertLessEqual(len(failures[0].get("error") or ""), 121)

    def test_allocate_web_replaces_prior_failures_with_retriever(self):
        history = ResearchHistory.from_snapshot(
            [
                {
                    "id": "evt_1",
                    "type": "verify_fail",
                    "action": {"command": "wmic", "args": ["cpu"]},
                    "result": {"ok": False, "error": "failed"},
                }
            ]
        )
        state = TaskState(
            open_questions=[
                {
                    "id": "q1",
                    "text": "温度",
                    "status": "open",
                    "related_events": ["evt_1"],
                }
            ],
            research_history=history,
        )
        legacy = {
            "prior_failures": [
                {
                    "question": "old",
                    "finding": "old",
                    "error": "X" * 400,
                    "command": "powershell",
                    "args": ["-Command", "long"],
                }
            ],
            "search_results": [{"title": "t", "snippet": "s" * 300}],
            "judge_reason": "R" * 500,
            "inventory": {"available_commands": ["powershell", "wmic"]},
        }
        allocated = allocate_web_candidate_materials(legacy, state)
        self.assertIn(
            allocated["_context_allocation"]["prior_failures_source"],
            ("retriever", "memory_recall"),
        )
        self.assertLessEqual(len(allocated["prior_failures"]), 1)
        self.assertLessEqual(len(allocated["search_results"]), 3)
        self.assertLessEqual(len(allocated.get("judge_reason") or ""), 161)

    def test_allocate_judge_removes_duplicate_unresolved(self):
        state = TaskState(
            open_questions=[{"id": "q1", "text": "gap", "status": "open"}],
        )
        materials = {
            "target_request": "CPU温度",
            "output": ["status"],
            "usable_findings": [],
            "insufficient_findings": [{"question": "q", "finding": "f"}],
            "unresolved": [{"question": "dup", "finding": "event:evt_x"}],
        }
        allocated, state_payload = allocate_judge_materials(materials, state)
        self.assertNotIn("unresolved", allocated)
        self.assertIn("open_questions", state_payload)

    def test_shadow_mode_sends_legacy_but_records_allocated(self):
        init_context_budget_shadow()
        materials = {
            "subject": {"tool_name": "cpu_temperature"},
            "items": [{"question": "CPU温度"}],
            "search_results": [],
            "inventory": {"available_commands": ["powershell"]},
            "rules": ["rule"],
        }
        state = TaskState(task="CPU温度")
        profile = {
            "context_limit": 4096,
            "num_predict": 2048,
            "prompt_style": "english_compact",
            "materials": {"compact_json": True},
        }
        with patch.dict(os.environ, {"AI_AGENT_CONTEXT_ALLOC_LIVE": "0"}, clear=False):
            prepared = prepare_context_allocation_call(
                build_web_candidate_messages,
                materials,
                state=state,
                profile=profile,
            )
            self.assertEqual(prepared["measurement"]["mode"], "shadow")
        self.assertIsNotNone(prepared["messages"])
        self.assertIsNotNone(prepared["measurement"]["legacy_chars"])
        self.assertIsNotNone(prepared["measurement"]["allocated_chars"])
        summary = finalize_context_budget_shadow({"calls": []})
        self.assertIn("summary", summary)

    def test_measure_prompt_sections_for_web(self):
        materials = {
            "subject": {"tool_name": "x"},
            "search_results": [{"title": "a", "snippet": "b"}],
            "rules": ["r"],
        }
        profile = {"prompt_style": "english_compact", "materials": {"compact_json": True}}
        measured = measure_prompt_sections(
            BUILDER_WEB,
            materials,
            state=TaskState(task="t"),
            profile=profile,
        )
        self.assertIn("system", measured["sections"])
        self.assertIn("action_local", measured["sections"])
        self.assertGreater(measured["total"], 0)

    def test_live_mode_uses_allocated_messages(self):
        materials = {
            "target_request": "CPU温度",
            "output": ["status"],
            "usable_findings": [],
            "insufficient_findings": [],
            "unresolved": [],
        }
        state = TaskState(task="CPU温度")
        profile = {
            "context_limit": 4096,
            "num_predict": 2048,
            "prompt_style": "english_compact",
            "materials": {"compact_json": True},
        }
        # 既定 live。明示なしでも allocated を送る。
        os.environ.pop("AI_AGENT_CONTEXT_ALLOC_LIVE", None)
        prepared = prepare_context_allocation_call(
            build_research_judge_messages,
            materials,
            state=state,
            profile=profile,
        )
        self.assertEqual(prepared["measurement"]["mode"], "live")
        self.assertIsNotNone(prepared["messages"])

    def test_headroom_gate_requires_reserved_800(self):
        self.assertTrue(headroom_gate_ok(800))
        self.assertTrue(headroom_gate_ok(803))
        self.assertFalse(headroom_gate_ok(3))
        self.assertFalse(headroom_gate_ok(799))

    def test_omit_hints_when_search_nonempty(self):
        state = TaskState(task="CPU温度")
        materials = {
            "empty_search": False,
            "route_hints": ["r1", "r2"],
            "exploration_hints": ["h1", "h2", "h3"],
            "search_results": [{"title": "t", "snippet": "s"}],
            "inventory": {"available_commands": ["powershell"]},
            "prior_failures": [],
            "judge_reason": "reason",
        }
        from tools.ai.llm.context_allocation import REDUCTION_STEPS

        allocated = allocate_web_candidate_materials(
            materials, state, reduction=REDUCTION_STEPS[1]
        )
        self.assertEqual(allocated.get("route_hints"), [])
        self.assertEqual(allocated.get("exploration_hints"), [])
        omitted = allocated["_context_allocation"]["omitted_categories"]
        self.assertIn("route_hints", omitted)
        self.assertIn("exploration_hints", omitted)

    def test_keep_exploration_hints_on_empty_search_at_omit_hints_level(self):
        state = TaskState(task="CPU温度")
        materials = {
            "empty_search": True,
            "route_hints": ["r1"],
            "exploration_hints": ["h1", "h2"],
            "search_results": [],
            "inventory": {"available_commands": ["powershell"]},
            "prior_failures": [],
        }
        from tools.ai.llm.context_allocation import REDUCTION_STEPS

        allocated = allocate_web_candidate_materials(
            materials, state, reduction=REDUCTION_STEPS[1]
        )
        self.assertEqual(allocated.get("route_hints"), [])
        self.assertTrue(allocated.get("exploration_hints"))

    def test_allocation_preserves_usable_findings(self):
        state = TaskState(
            open_questions=[{"id": "q1", "text": "gap", "status": "open"}]
        )
        usable = [
            {
                "question": "CPU温度",
                "finding": "ok",
                "evidence": {"command": "wmic", "args": [], "sample": ["42"]},
            }
        ]
        materials = {
            "target_request": "CPU温度",
            "output": ["status"],
            "usable_findings": usable,
            "insufficient_findings": [{"question": "x"}] * 10,
            "unresolved": [{"question": "dup"}],
        }
        from tools.ai.llm.context_allocation import REDUCTION_STEPS

        allocated, _ = allocate_judge_materials(
            materials, state, reduction=REDUCTION_STEPS[-1]
        )
        self.assertEqual(len(allocated["usable_findings"]), 1)
        self.assertLessEqual(len(allocated["insufficient_findings"]), 1)
        self.assertNotIn("unresolved", allocated)

    def test_fat_web_prompt_secures_actual_headroom(self):
        history_events = []
        related = []
        for i in range(8):
            eid = f"evt_{i}"
            related.append(eid)
            history_events.append(
                {
                    "id": eid,
                    "type": "verify_fail",
                    "action": {
                        "command": "powershell",
                        "args": ["-Command", f"Get-Thing{i} " + ("x" * 80)],
                    },
                    "result": {"ok": False, "error": "err" * 40, "stderr": "E" * 400},
                }
            )
        history = ResearchHistory.from_snapshot(history_events)
        state = TaskState(
            task="CPU温度を取得",
            decisions=[
                {"key": "status.meaning", "value": "temperature"},
                {"key": "status.unit", "value": "C"},
            ],
            open_questions=[
                {
                    "id": "q1",
                    "text": "CPU温度の取得方法",
                    "status": "open",
                    "related_events": related,
                }
            ],
            research_history=history,
            banned_actions=[{"command": "powershell", "reason": "failed"}] * 3,
        )
        materials = {
            "subject": {"tool_name": "cpu_temperature", "subcategory": "hardware"},
            "items": [{"question": "CPU温度"}] * 3,
            "followup_questions": ["温度センサー", "WMI温度"],
            "empty_search": False,
            "search_results": [
                {"title": f"hit{i}", "snippet": "s" * 200} for i in range(10)
            ],
            "inventory": {
                "available_commands": ["powershell", "wmic", "nvidia-smi"]
            },
            "rules": ["rule"] * 8,
            "rejected_commands": [
                {"command": "powershell", "args": [f"a{i}"]} for i in range(12)
            ],
            "exploration_hints": ["hint"] * 10,
            "route_hints": ["route"] * 12,
            "judge_reason": "R" * 400,
            "prior_failures": [
                {
                    "question": "q",
                    "finding": "f",
                    "error": "E" * 300,
                    "command": "powershell",
                    "args": ["x"],
                }
            ]
            * 5,
            "environment": {"platform": "windows"},
            "search_keywords": ["cpu", "temperature"],
        }
        profile = {
            "context_limit": 4096,
            "num_predict": 2048,
            "prompt_style": "english_compact",
            "materials": {"compact_json": True},
        }
        prepared = prepare_context_allocation_call(
            build_web_candidate_messages,
            materials,
            state=state,
            profile=profile,
        )
        m = prepared["measurement"]
        self.assertGreaterEqual(m["actual_headroom"], RESERVED_HEADROOM_CHARS)
        self.assertTrue(m["headroom_gate_ok"])
        self.assertFalse(m["allocated_overflow"])
        self.assertIn("categories", m.get("allocation") or {})


if __name__ == "__main__":
    unittest.main()
