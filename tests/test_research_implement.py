import inspect
import unittest

from research.llm_benchmarks.environment_benchmark import contains_forbidden_answer
from research.llm_benchmarks.research_implement_classify import (
    CREATE_REQUEST,
    inspect_code_generated,
    inspect_code_matches,
    inspect_create_result,
    inspect_fail_stage,
    inspect_judge_adopted,
    inspect_pipeline_stages,
    inspect_registry,
    inspect_research_method,
    inspect_runs,
    start_from_clarity_state,
    summarize_verified_round,
)
from research.llm_benchmarks import research_implement


FINDING = {
    "evidence": {
        "command": "powershell",
        "args": [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse",
        ],
        "sample": ["PercentCommittedBytesInUse", "--------------------------", "39"],
    }
}

MATCHING_CODE = """
import subprocess
def get_memory_status():
    result = subprocess.run([
        'powershell', '-NoProfile', '-NonInteractive', '-Command',
        'Get-CimInstance -Class Win32_PerfFormattedData_PerfOS_Memory | Select PercentCommittedBytesInUse'
    ], capture_output=True, text=True)
    return {'status': result.stdout.strip()}
"""

STUB_CODE = "def get_memory_status():\n    return {'status': '未実装'}\n"

PROPOSAL = {
    "name": "get_memory_status",
    "module": "tools.system.memory.memory_status",
    "function": "get_memory_status",
    "output": ["status"],
}


class ResearchImplementClassifyTests(unittest.TestCase):
    def test_request_is_memory_usage_and_does_not_teach_command(self):
        self.assertIn("メモリ使用率", CREATE_REQUEST)
        self.assertFalse(contains_forbidden_answer(CREATE_REQUEST))

    def test_starts_from_clarity_usage_reply(self):
        started = start_from_clarity_state()
        self.assertEqual(started["request"], CREATE_REQUEST)
        self.assertTrue(started["user_state"]["ok"], started["user_state"])
        self.assertEqual(started["state"].task, CREATE_REQUEST)
        meaning = started["state"].get_decision("status.meaning")
        self.assertEqual(meaning["value"], "Windowsのメモリ使用率")
        self.assertEqual(meaning["source"], "user")

    def test_research_method_needs_command_and_sample(self):
        empty = inspect_research_method({"usable_findings": []})
        self.assertFalse(empty["ok"])
        ready = inspect_research_method({"usable_findings": [FINDING]})
        self.assertTrue(ready["ok"])
        self.assertEqual(ready["usable_count"], 1)

    def test_judge_adopted_needs_satisfies_and_sufficient(self):
        judgments = [{"satisfies_request": True, "missing": []}]
        self.assertFalse(
            inspect_judge_adopted(judgments, research_sufficient=False)["ok"]
        )
        self.assertFalse(
            inspect_judge_adopted(
                [{"satisfies_request": False, "missing": ["usage"]}],
                research_sufficient=True,
            )["ok"]
        )
        self.assertTrue(
            inspect_judge_adopted(judgments, research_sufficient=True)["ok"]
        )

    def test_code_generated_and_matches_research_method(self):
        self.assertFalse(inspect_code_generated({"code": ""})["ok"])
        self.assertTrue(inspect_code_generated({"code": MATCHING_CODE})["ok"])
        matched = inspect_code_matches(
            MATCHING_CODE, {"usable_findings": [FINDING]}
        )
        self.assertTrue(matched["ok"])
        self.assertTrue(matched["finding_adopted"])
        stub = inspect_code_matches(STUB_CODE, {"usable_findings": [FINDING]})
        self.assertFalse(stub["ok"])

    def test_registry_needs_existing_tool_structure(self):
        registered = {
            "result": "OK",
            "path": "tools/system/memory/memory_status.py",
            "registered_name": "get_memory_status",
        }
        ok = inspect_registry(
            registered, PROPOSAL, path_exists=True, in_registry=True
        )
        self.assertTrue(ok["ok"])
        self.assertTrue(ok["structure"])
        missing_file = inspect_registry(
            registered, PROPOSAL, path_exists=False, in_registry=True
        )
        self.assertFalse(missing_file["ok"])
        wrong_module = inspect_registry(
            registered,
            {**PROPOSAL, "module": "tools.ai.memory.memory_status"},
            path_exists=True,
            in_registry=True,
        )
        self.assertFalse(wrong_module["ok"])

    def test_runs_means_the_tool_executed(self):
        self.assertFalse(inspect_runs(None)["ok"])
        self.assertFalse(
            inspect_runs({"status": "fail", "error": "boom", "return_value": None})["ok"]
        )
        ran = inspect_runs(
            {"status": "pass", "return_value": {"status": 43.2}}
        )
        self.assertTrue(ran["ok"])
        self.assertTrue(ran["is_dict"])

    def test_fail_stage_splits_research_judge_implementation(self):
        research_fail = inspect_create_result(
            research={"usable_findings": []},
            judgments=[{"satisfies_request": False}],
            research_sufficient=False,
        )
        self.assertEqual(research_fail["fail_stage"], "research")

        judge_fail = inspect_create_result(
            research={
                "usable_findings": [],
                "insufficient_findings": [FINDING],
            },
            judgments=[{"satisfies_request": False, "missing": ["usage"]}],
            research_sufficient=False,
        )
        self.assertEqual(judge_fail["fail_stage"], "judge")
        self.assertTrue(judge_fail["checks"]["research_method"]["ok"])

        impl_fail = inspect_create_result(
            research={"usable_findings": [FINDING]},
            judgments=[{"satisfies_request": True}],
            research_sufficient=True,
            payload={"code": STUB_CODE, "function": "get_memory_status"},
            proposal=PROPOSAL,
        )
        self.assertEqual(impl_fail["fail_stage"], "implementation")
        self.assertTrue(impl_fail["checks"]["research_method"]["ok"])
        self.assertTrue(impl_fail["checks"]["judge_adopted"]["ok"])
        self.assertTrue(impl_fail["checks"]["code_generated"]["ok"])
        self.assertFalse(impl_fail["checks"]["code_matches"]["ok"])

    def test_all_six_checks_pass_without_repair(self):
        inspected = inspect_create_result(
            research={"usable_findings": [FINDING]},
            judgments=[{"satisfies_request": True, "missing": []}],
            research_sufficient=True,
            payload={
                "code": MATCHING_CODE,
                "function": "get_memory_status",
                "path": "tools/system/memory/memory_status.py",
            },
            registered={
                "result": "OK",
                "path": "tools/system/memory/memory_status.py",
                "registered_name": "get_memory_status",
            },
            proposal=PROPOSAL,
            path_exists=True,
            in_registry=True,
            test_result={"status": "pass", "return_value": {"status": 43.2}},
            repaired=False,
        )
        self.assertIsNone(inspected["fail_stage"])
        self.assertTrue(inspected["ok"])
        self.assertFalse(inspected["repaired"])

    def test_proposal_error_is_not_blamed_on_research(self):
        inspected = inspect_create_result(proposal_error="no_proposal")
        self.assertEqual(inspected["fail_stage"], "proposal")
        self.assertFalse(inspected["ok"])

    def test_benchmark_does_not_call_repair(self):
        source = inspect.getsource(research_implement)
        self.assertNotIn("repair_tool", source)
        self.assertNotIn("build_repair_messages", source)
        self.assertNotIn("apply_repair", source)
        self.assertIn('repair": "skipped"', source)

    def test_pipeline_stages_track_retry_loop(self):
        rounds = [
            {
                "round": 1,
                "candidate_count": 1,
                "verified_count": 1,
                "verifier_failure": True,
                "satisfies_request": False,
                "judge_grade": "A",
            },
            {
                "round": 2,
                "candidate_count": 1,
                "verified_count": 1,
                "verifier_failure": False,
                "satisfies_request": True,
                "judge_grade": "FAIL",
            },
        ]
        pipeline = inspect_pipeline_stages(
            user_state={"ok": True},
            research_rounds=rounds,
            research={"usable_findings": [FINDING]},
            judgments=[{"satisfies_request": True}],
            research_sufficient=True,
            payload={"code": MATCHING_CODE},
            test_result={"status": "pass", "return_value": {"status": 43.2}},
        )
        stages = pipeline["stages"]
        self.assertTrue(stages["state_held"]["ok"])
        self.assertTrue(stages["candidates_generated"]["ok"])
        self.assertTrue(stages["verifier_ran"]["ok"])
        self.assertTrue(stages["verifier_failure_detected"]["ok"])
        self.assertTrue(stages["judge_a_quality"]["ok"])
        self.assertTrue(stages["research_retried"]["ok"])
        self.assertTrue(stages["usable_finding"]["ok"])
        self.assertTrue(stages["judge_adopted"]["ok"])
        self.assertTrue(stages["implementation_code"]["ok"])
        self.assertTrue(stages["tool_runs"]["ok"])
        self.assertTrue(pipeline["ok"])

    def test_summarize_verified_round_detects_failure(self):
        summary = summarize_verified_round(
            {
                "candidates": [{"command": "powershell"}],
                "verified": {
                    "results": [
                        {
                            "confidence": "low",
                            "evidence": {"sample": [], "error": "0 で除算"},
                        }
                    ]
                },
            }
        )
        self.assertEqual(summary["candidate_count"], 1)
        self.assertTrue(summary["any_failure"])


if __name__ == "__main__":
    unittest.main()
