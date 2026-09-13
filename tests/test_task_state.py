import unittest

from research.llm_benchmarks.persistence_benchmark import matches_expect
from tools.ai.llm.adapter import (
    build_implement_messages,
    build_repair_messages,
    build_research_judge_messages,
    build_state_query_messages,
)
from tools.ai.prompts.state import STATE_CONTRACT
from tools.ai.state.decision_store import apply_judgment, extra_keys_from_proposal
from tools.ai.state.task_state import TaskState, empty_state
from tools.system.config import get_llm_profile


class TaskStateTests(unittest.TestCase):
    def test_empty_shape(self):
        payload = empty_state("Windowsのメモリ使用率を取得するToolを追加する")
        self.assertEqual(
            set(payload),
            {
                "task",
                "facts",
                "decisions",
                "selected_findings",
                "constraints",
                "open_questions",
                "unresolved",
            },
        )
        self.assertEqual(payload["decisions"], [])

    def test_does_not_overwrite_existing_key(self):
        state = TaskState(task="t")
        self.assertTrue(
            state.add_decision(
                "status.unit", "%", source="judge", confidence="confirmed"
            )
        )
        self.assertFalse(
            state.add_decision(
                "status.unit", "bytes", source="judge", confidence="confirmed"
            )
        )
        self.assertEqual(state.get_decision("status.unit")["value"], "%")


class DecisionStoreTests(unittest.TestCase):
    def test_promotes_only_when_satisfied(self):
        state = TaskState(task="t")
        apply_judgment(
            state,
            {
                "satisfies_request": False,
                "proposed_decisions": [
                    {"key": "status.unit", "value": "%"},
                ],
            },
        )
        self.assertIsNone(state.get_decision("status.unit"))
        apply_judgment(
            state,
            {
                "satisfies_request": True,
                "proposed_decisions": [
                    {"key": "status.meaning", "value": "memory usage percentage"},
                    {"key": "status.unit", "value": "%"},
                    {"key": "status.range", "value": "0-100"},
                ],
            },
        )
        self.assertEqual(state.get_decision("status.unit")["value"], "%")
        self.assertEqual(state.get_decision("status.unit")["source"], "judge")
        self.assertEqual(state.get_decision("status.unit")["confidence"], "confirmed")

    def test_ignores_llm_decisions_field(self):
        state = TaskState(task="t")
        apply_judgment(
            state,
            {
                "satisfies_request": True,
                "decisions": [
                    {
                        "key": "status.unit",
                        "value": "%",
                        "source": "judge",
                        "confidence": "confirmed",
                    }
                ],
            },
        )
        self.assertIsNone(state.get_decision("status.unit"))

    def test_strips_llm_confidence_and_rejects_commands(self):
        state = TaskState(task="t")
        apply_judgment(
            state,
            {
                "satisfies_request": True,
                "proposed_decisions": [
                    {
                        "key": "status.unit",
                        "value": "%",
                        "confidence": "guess",
                        "source": "llm",
                    },
                    {
                        "key": "status.meaning",
                        "value": "Get-CimInstance Win32_OperatingSystem",
                    },
                    {"key": "status.command", "value": "powershell"},
                ],
            },
        )
        self.assertEqual(state.get_decision("status.unit")["confidence"], "confirmed")
        self.assertEqual(state.get_decision("status.unit")["source"], "judge")
        self.assertIsNone(state.get_decision("status.meaning"))
        self.assertIsNone(state.get_decision("status.command"))

    def test_extra_keys_from_proposal_output(self):
        keys = extra_keys_from_proposal({"output": ["usage"]})
        self.assertIn("usage.unit", keys)
        state = TaskState(task="t")
        apply_judgment(
            state,
            {
                "satisfies_request": True,
                "proposed_decisions": [{"key": "usage.unit", "value": "%"}],
            },
            extra_keys=keys,
        )
        self.assertEqual(state.get_decision("usage.unit")["value"], "%")


class StatePromptTests(unittest.TestCase):
    def test_omits_state_when_not_passed(self):
        messages = build_repair_messages(
            {"current_source": "source"},
            profile=get_llm_profile("qwen3_8b"),
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertNotIn("TASK STATE", joined)
        self.assertNotIn("STATE は確定済み", joined)
        self.assertIn("TASK MATERIALS", joined)

    def test_state_comes_before_materials(self):
        state = TaskState(task="Windowsのメモリ使用率を取得するToolを追加する")
        state.add_decision(
            "status.unit", "%", source="judge", confidence="confirmed"
        )
        messages = build_implement_messages(
            {"target_request": "実装して", "usable_findings": []},
            profile=get_llm_profile("qwen3_8b"),
            state=state,
        )
        user = messages[1]["content"]
        self.assertLess(user.find("TASK STATE"), user.find("TASK MATERIALS"))
        self.assertIn("status.unit", user)
        self.assertIn("STATE は確定済み", messages[0]["content"])
        for item in STATE_CONTRACT:
            self.assertIn(item["ja"], messages[0]["content"])

    def test_repair_keeps_state(self):
        state = {
            "task": "t",
            "decisions": [
                {
                    "key": "status.meaning",
                    "value": "memory usage percentage",
                    "source": "judge",
                    "confidence": "confirmed",
                }
            ],
        }
        first = build_repair_messages({"current_source": "v1"}, state=state)
        second = build_repair_messages({"current_source": "v2"}, state=state)
        self.assertIn("memory usage percentage", first[1]["content"])
        self.assertIn("memory usage percentage", second[1]["content"])

    def test_baseline_only_state_differs(self):
        from tools.system.llm_failure_memory import load_environment_case

        case = load_environment_case("persist_status_unit_baseline")
        round_spec = case["rounds"][0]
        materials = dict(round_spec["materials"])
        materials["question"] = round_spec["question"]
        without = build_state_query_messages(materials)
        with_state = build_state_query_messages(materials, state=case["state"])
        without_user = without[1]["content"]
        with_user = with_state[1]["content"]
        self.assertNotIn("TASK STATE", without_user)
        self.assertIn("TASK STATE", with_user)
        self.assertLess(with_user.find("TASK STATE"), with_user.find("TASK MATERIALS"))
        self.assertIn("Windowsのメモリ使用率", with_user)
        self.assertIn("43.2", without_user)
        self.assertIn("43.2", with_user)
        self.assertIn(round_spec["question"], without_user)
        self.assertIn(round_spec["question"], with_user)

    def test_judge_shape_includes_proposed_decisions(self):
        messages = build_research_judge_messages(
            {"target_request": "メモリ使用率", "usable_findings": []}
        )
        joined = "\n".join(item["content"] for item in messages)
        self.assertIn("proposed_decisions", joined)

    def test_persistence_tokens(self):
        self.assertTrue(matches_expect("単位は % です", ["%", "percent"]))
        self.assertFalse(matches_expect("success or error", ["%", "percent"]))


if __name__ == "__main__":
    unittest.main()
