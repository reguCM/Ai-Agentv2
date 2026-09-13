import json
import unittest

from tools.ai.llm.adapter import build_clarity_messages
from tools.ai.prompts.create import CLARITY_CONTRACT
from tools.ai.state.decision_store import REQUEST_DECISION_KEYS, apply_user_option
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.clarity import (
    create_clarity_materials,
    normalize_clarity,
)
from tools.system.config import get_llm_profile, get_pipeline
from tools.system.tool_builder.clarity import (
    match_option,
    next_clarity_step,
    run_clarity_gate,
)


MEMORY_OPTIONS = [
    {
        "id": "usage",
        "label": "使用率",
        "decisions": [{"key": "request.metric", "value": "使用率"}],
    },
    {
        "id": "free",
        "label": "空き容量",
        "decisions": [{"key": "request.metric", "value": "空き容量"}],
    },
    {
        "id": "total",
        "label": "総容量",
        "decisions": [{"key": "request.metric", "value": "総容量"}],
    },
]


class ClarityNormalizeTests(unittest.TestCase):
    def test_materials_are_request_and_conversation_only(self):
        materials = create_clarity_materials(
            "メモリを取得するToolを作って",
            [
                {"role": "assistant", "text": "どれを取得しますか？"},
                {"role": "user", "text": "使用率"},
                {"role": "system", "text": "drop"},
            ],
        )
        self.assertEqual(set(materials), {"target_request", "conversation"})
        self.assertNotIn("usable_findings", materials)
        self.assertEqual(len(materials["conversation"]), 2)

    def test_unknown_status_does_not_become_clear(self):
        judgment = normalize_clarity({"status": "maybe", "question": ""})
        self.assertEqual(judgment["status"], "insufficient_information")
        self.assertEqual(next_clarity_step(judgment), "ask_user")

    def test_clear_drops_options(self):
        judgment = normalize_clarity(
            {
                "status": "clear",
                "question": "残すな",
                "options": MEMORY_OPTIONS,
            }
        )
        self.assertEqual(judgment["status"], "clear")
        self.assertEqual(judgment["question"], "")
        self.assertEqual(judgment["options"], [])
        self.assertEqual(next_clarity_step(judgment), "research")

    def test_three_statuses_route(self):
        self.assertEqual(next_clarity_step({"status": "clear"}), "research")
        self.assertEqual(
            next_clarity_step({"status": "needs_clarification"}), "ask_user"
        )
        self.assertEqual(
            next_clarity_step({"status": "insufficient_information"}), "ask_user"
        )

    def test_option_decisions_keep_request_keys_only(self):
        judgment = normalize_clarity(
            {
                "status": "needs_clarification",
                "question": "どれを取得しますか？",
                "options": [
                    {
                        "id": "usage",
                        "label": "使用率",
                        "decisions": [
                            {"key": "request.metric", "value": "使用率"},
                            {"key": "status.command", "value": "powershell"},
                        ],
                    }
                ],
            }
        )
        self.assertEqual(
            judgment["options"][0]["decisions"],
            [{"key": "request.metric", "value": "使用率"}],
        )


class ClarityMatchTests(unittest.TestCase):
    def test_matches_label(self):
        self.assertEqual(match_option(MEMORY_OPTIONS, "使用率")["id"], "usage")
        self.assertEqual(match_option(MEMORY_OPTIONS, "usage")["id"], "usage")

    def test_ambiguous_capacity_does_not_match(self):
        self.assertIsNone(match_option(MEMORY_OPTIONS, "容量"))


class ClarityGateTests(unittest.TestCase):
    def test_clear_request_goes_to_research_without_asking(self):
        asked = []

        def complete(materials, state):
            self.assertEqual(set(materials), {"target_request", "conversation"})
            return {
                "status": "clear",
                "options": MEMORY_OPTIONS,
                "proposed_decisions": [
                    {"key": "request.metric", "value": "使用率"},
                ],
            }

        result = run_clarity_gate(
            "Windowsのメモリ使用率を取得するToolを追加してください",
            ask=lambda question, options: asked.append(question) or "x",
            complete=complete,
        )
        self.assertEqual(result["next_step"], "research")
        self.assertEqual(asked, [])
        self.assertIsNone(result["state"].get_decision("request.metric"))

    def test_memory_metric_asks_then_promotes_user_choice(self):
        calls = []

        def complete(materials, state):
            calls.append(materials)
            if len(calls) == 1:
                return {
                    "status": "needs_clarification",
                    "question": "使用率・空き容量・総容量のどれを取得しますか？",
                    "options": MEMORY_OPTIONS,
                    "proposed_decisions": [
                        {"key": "request.metric", "value": "使用率"},
                    ],
                }
            self.assertEqual(materials["conversation"][-1]["text"], "使用率です")
            return {"status": "clear", "proposed_decisions": [{"key": "request.metric", "value": "空き容量"}]}

        result = run_clarity_gate(
            "Windowsのメモリを取得するToolを作って",
            ask=lambda question, options: "使用率です",
            complete=complete,
        )
        self.assertEqual(result["next_step"], "research")
        self.assertEqual(len(calls), 2)
        state = result["state"]
        self.assertEqual(state.get_decision("status.meaning")["value"], "Windowsのメモリ使用率")
        self.assertEqual(state.get_decision("status.unit")["value"], "%")
        self.assertEqual(state.get_decision("status.range")["value"], "0-100")
        self.assertEqual(state.get_decision("status.unit")["source"], "user")
        self.assertEqual(state.get_decision("request.metric")["value"], "使用率")

    def test_vague_request_asks_purpose(self):
        def complete(materials, state):
            return {
                "status": "insufficient_information",
                "question": "何を取得・操作するToolが必要ですか？",
            }

        result = run_clarity_gate(
            "いい感じのToolを作って",
            ask=lambda question, options: None,
            complete=complete,
        )
        self.assertEqual(result["next_step"], "ask_user")
        self.assertEqual(result["status"], "insufficient_information")
        self.assertIn("何を取得", result["judgment"]["question"])

    def test_does_not_research_when_user_does_not_reply(self):
        result = run_clarity_gate(
            "メモリを取得するToolを作って",
            ask=lambda question, options: "",
            complete=lambda materials, state: {
                "status": "needs_clarification",
                "question": "どれを取得しますか？",
                "options": MEMORY_OPTIONS,
            },
        )
        self.assertEqual(result["next_step"], "ask_user")
        self.assertIsNone(result["state"].get_decision("request.metric"))

    def test_does_not_promote_llm_clear_decisions(self):
        state = TaskState(task="t")
        apply_user_option(
            state,
            {
                "decisions": [
                    {"key": "request.metric", "value": "使用率"},
                    {"key": "status.unit", "value": "%"},
                ]
            },
        )
        self.assertEqual(state.get_decision("request.metric")["source"], "user")
        self.assertIsNone(state.get_decision("status.unit"))
        self.assertEqual(REQUEST_DECISION_KEYS, {
            "request.subject",
            "request.action",
            "request.metric",
            "request.target",
        })

    def test_usage_reply_writes_status_without_llm_decisions(self):
        from tools.ai.state.user_choice import apply_user_reply

        state = TaskState(task="Windowsのメモリを取得するToolを作って")
        apply_user_reply(
            state,
            "使用率です",
            option={
                "id": "usage",
                "label": "使用率",
                "decisions": [
                    {"key": "status.unit", "value": "bytes"},
                    {"key": "request.metric", "value": "空き容量"},
                ],
            },
        )
        self.assertEqual(state.get_decision("status.meaning")["value"], "Windowsのメモリ使用率")
        self.assertEqual(state.get_decision("status.unit")["value"], "%")
        self.assertEqual(state.get_decision("status.range")["value"], "0-100")
        self.assertEqual(state.get_decision("status.meaning")["source"], "user")
        self.assertEqual(state.get_decision("request.metric")["value"], "使用率")

    def test_ambiguous_capacity_reply_does_not_promote(self):
        from tools.ai.state.user_choice import apply_user_reply

        state = TaskState(task="t")
        apply_user_reply(state, "容量", option=None)
        self.assertIsNone(state.get_decision("status.meaning"))
        self.assertIsNone(state.get_decision("request.metric"))


class ClarityPromptTests(unittest.TestCase):
    def test_contract_forbids_research_resolution(self):
        ids = [item["id"] for item in CLARITY_CONTRACT]
        self.assertIn("no_research", ids)
        self.assertIn("no_default", ids)
        self.assertIn("scope", ids)
        self.assertIn("user_decides", ids)
        messages = build_clarity_messages(
            create_clarity_materials("メモリを取得するToolを作って"),
            profile=get_llm_profile("qwen3_8b"),
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertIn("何を作りたいか", joined)
        self.assertIn("調査しない", joined)
        self.assertIn("PROJECT CONTEXT", joined)
        self.assertIn("implementation_method_selection", joined)
        self.assertIn("Agent", joined)
        self.assertNotIn("PowerShellかWMIかCIM", joined)
        self.assertNotIn("usable_findings", joined)
        self.assertLess(joined.find("PROJECT CONTEXT"), joined.find("TASK MATERIALS"))

    def test_pipeline_has_clarity_routing(self):
        pipeline = get_pipeline()
        self.assertEqual(pipeline["max_clarity_rounds"], 5)
        self.assertEqual(
            pipeline["clarity_statuses"],
            ["clear", "needs_clarification", "insufficient_information"],
        )
        self.assertEqual(pipeline["clarity_next_steps"], ["research", "ask_user"])
        context = pipeline.get("project_context") or {}
        self.assertEqual(context.get("implementation_method_selection"), "Agent")
        self.assertEqual(context.get("os"), "Windows")


class ClarityBenchmarkGuardTests(unittest.TestCase):
    def test_cases_match_expected_status(self):
        from tools.system.llm_failure_memory import load_environment_case

        expected = {
            "clarity_memory_usage": (
                "Windowsのメモリ使用率を取得するTool",
                "clear",
                "research",
            ),
            "clarity_memory_ambiguous": (
                "Windowsのメモリを取得するTool",
                "needs_clarification",
                "ask_user",
            ),
            "clarity_memory_vague": (
                "便利なメモリToolを作って",
                "insufficient_information",
                "ask_user",
            ),
        }
        for case_id, (request, status, step) in expected.items():
            case = load_environment_case(case_id)
            self.assertEqual(case["request"], request)
            self.assertEqual(case["expect_status"], status)
            self.assertEqual(case["expect_next_step"], step)
            packed = json.dumps(case, ensure_ascii=False).lower()
            self.assertNotIn("usable_findings", packed)
            self.assertNotIn("win32_operatingsystem", packed)
            if case_id == "clarity_memory_ambiguous":
                self.assertTrue(case.get("expect_any"))

    def test_real_prompt_is_isolated_from_research(self):
        from research.llm_benchmarks.clarity_classify import inspect_research_isolation

        materials = create_clarity_materials("Windowsのメモリを取得するTool")
        messages = build_clarity_messages(
            materials, profile=get_llm_profile("qwen3_8b")
        )
        report = inspect_research_isolation(messages, materials)
        self.assertTrue(report["ok"], report["leaks"])

    def test_isolation_detects_injected_findings(self):
        from research.llm_benchmarks.clarity_classify import inspect_research_isolation

        materials = create_clarity_materials("Windowsのメモリを取得するTool")
        materials["usable_findings"] = [
            {
                "evidence": {
                    "command": "powershell",
                    "sample": ["Get-CimInstance Win32_OperatingSystem"],
                }
            }
        ]
        messages = build_clarity_messages(
            materials, profile=get_llm_profile("qwen3_8b")
        )
        report = inspect_research_isolation(messages, materials)
        self.assertFalse(report["ok"])
        kinds = {item["kind"] for item in report["leaks"]}
        self.assertIn("material_key", kinds)
        self.assertIn("research_field", kinds)
        self.assertIn("research_answer", kinds)

    def test_ambiguous_clear_is_resolved_without_asking(self):
        from research.llm_benchmarks.clarity_classify import classify_clarity_trial

        labels = classify_clarity_trial(
            {"status": "clear"},
            expect_status="needs_clarification",
            isolation={"ok": True},
        )
        self.assertTrue(labels["resolved_without_asking"])
        self.assertFalse(labels["ok"])

    def test_wrong_windows_app_question_misses_expect(self):
        from research.llm_benchmarks.clarity_classify import classify_clarity_trial

        labels = classify_clarity_trial(
            {
                "status": "needs_clarification",
                "question": "Which Windows tool?",
                "options": [
                    {"id": "a", "label": "Use Task Manager"},
                    {"id": "b", "label": "Use PowerShell Command"},
                ],
            },
            expect_status="needs_clarification",
            isolation={"ok": True},
            expect_any=["使用率", "空き", "総容量", "usage", "free", "total"],
        )
        self.assertTrue(labels["status_ok"])
        self.assertTrue(labels["delegated_method"])
        self.assertFalse(labels["did_not_delegate_method"])
        self.assertFalse(labels["user_decision_question"])
        self.assertFalse(labels["ok"])

    def test_metric_question_is_user_decision(self):
        from research.llm_benchmarks.clarity_classify import classify_clarity_trial

        labels = classify_clarity_trial(
            {
                "status": "needs_clarification",
                "question": "使用率、空き容量、総容量のどれを取得しますか？",
                "options": [
                    {"id": "usage", "label": "使用率"},
                    {"id": "free", "label": "空き容量"},
                    {"id": "total", "label": "総容量"},
                ],
            },
            expect_status="needs_clarification",
            isolation={"ok": True},
            context={"ok": True},
            expect_any=["使用率", "空き", "総容量", "usage", "free", "total"],
        )
        self.assertTrue(labels["user_decision_question"])
        self.assertFalse(labels["delegated_method"])
        self.assertTrue(labels["ok"])

    def test_clarity_injects_context_repair_does_not(self):
        from tools.ai.llm.adapter import build_repair_messages

        clarity = build_clarity_messages(
            create_clarity_materials("メモリ使用率を取得するTool"),
            profile=get_llm_profile("qwen3_8b"),
        )
        repair = build_repair_messages(
            {"current_source": "source"},
            profile=get_llm_profile("qwen3_8b"),
        )
        clarity_text = "\n".join(item["content"] for item in clarity)
        repair_text = "\n".join(item["content"] for item in repair)
        self.assertIn("PROJECT CONTEXT", clarity_text)
        self.assertNotIn("PROJECT CONTEXT", repair_text)

    def test_benchmark_module_does_not_call_research(self):
        from pathlib import Path

        source = Path("research/llm_benchmarks/clarity_benchmark.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("research_tool", source)
        self.assertNotIn("web_research", source)
        self.assertNotIn("create_research_judgment", source)
        self.assertNotIn("usable_findings", source)


if __name__ == "__main__":
    unittest.main()
