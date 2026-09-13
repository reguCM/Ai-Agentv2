"""Phase D-1a: 観測専用（AUTO 非拡大）のテスト。"""

import inspect
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.ai.state.compatibility import COMPAT_CONFIRMED
from tools.ai.state.execution_gate import decide_execution_gate
from tools.ai.state.execution_observation import (
    append_observation_log,
    begin_execution_observation,
    build_observation_record,
    finalize_execution_observation,
    load_observation_log,
    new_execution_id,
)
from tools.ai.state.git_workspace_facts import collect_git_workspace_facts
from tools.ai.state.resource_probe import (
    build_resource_assessment_from_probe,
    diff_resource_snapshots,
    probe_environment_resources,
)
from tools.ai.state.safety_assessment import DANGEROUS, SAFE
from tools.ai.state.trusted_personal_policy import (
    MODE_DEFAULT,
    MODE_TRUSTED_PERSONAL,
    POLICY_AUTO,
    evaluate_trusted_personal_policy,
)
from tools.system.tool_builder.research.verify import evaluate_candidate_gate


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _safe_limited():
    return {
        "status": SAFE,
        "machine_assessed": SAFE,
        "side_effects": ["read_query"],
        "network_access": "none",
        "privilege": "none",
        "rationale_codes": ["matched_readonly_allowlist"],
    }


def _dangerous():
    return {
        "status": DANGEROUS,
        "machine_assessed": DANGEROUS,
        "side_effects": ["filesystem_delete"],
        "network_access": "none",
        "privilege": "unknown",
        "rationale_codes": ["dangerous_token"],
    }


class GitFactsD1aTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        _git(self.root, "init")
        _git(self.root, "config", "user.email", "d1a@test.local")
        _git(self.root, "config", "user.name", "d1a")
        (self.root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        _git(self.root, "add", "tracked.txt", ".gitignore")
        _git(self.root, "commit", "-m", "init")
        (self.root / "untracked.txt").write_text("u\n", encoding="utf-8")
        (self.root / "ignored.txt").write_text("i\n", encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_git_facts_collect_and_distinguish(self):
        facts = collect_git_workspace_facts(
            [
                str(self.root / "tracked.txt"),
                str(self.root / "untracked.txt"),
                str(self.root / "ignored.txt"),
            ],
            start_path=str(self.root),
        )
        self.assertTrue(facts["in_git_repo"])
        self.assertEqual(
            Path(facts["repo_root"]).resolve(),
            self.root.resolve(),
        )
        self.assertTrue(facts["head_exists"])
        self.assertTrue(any("tracked.txt" in p for p in facts["tracked_targets"]))
        self.assertTrue(any("untracked.txt" in p for p in facts["untracked_targets"]))
        self.assertTrue(any("ignored.txt" in p for p in facts["ignored_targets"]))
        self.assertFalse(facts["targets_covered"])
        reasons = {u["reason"] for u in facts["uncovered_targets"]}
        self.assertIn("untracked_not_restorable_via_git", reasons)
        self.assertIn("ignored_not_assumed_restorable", reasons)
        # Git があるだけでは可逆推定しない
        self.assertIn("git_presence_is_not_safety_proof", facts["rationale_codes"])

    def test_targets_covered_only_when_all_tracked(self):
        facts = collect_git_workspace_facts(
            [str(self.root / "tracked.txt")],
            start_path=str(self.root),
        )
        self.assertTrue(facts["targets_covered"])
        self.assertEqual(facts["uncovered_targets"], [])
        self.assertTrue(facts["restore_mechanism_available"])
        # メカニズム有と targets_covered は別フィールド
        self.assertIn("restore_mechanisms", facts)


class ResourceProbeD1aTests(unittest.TestCase):
    def test_probe_disk_memory_fields(self):
        res = probe_environment_resources()
        self.assertEqual(res["source"], "local_probe")
        self.assertIn("disk_free_bytes", res)
        self.assertIn("disk_free_ratio", res)
        self.assertIn("memory_available_bytes", res)
        self.assertIn("gpu_memory_free_bytes", res)
        self.assertIn("cpu_load", res)
        self.assertIn("gpu_utilization", res)
        self.assertIn("active_processes", res)
        # 値は数値か unknown（欠測を safe にしない）
        for key in (
            "disk_free_bytes",
            "memory_available_bytes",
            "gpu_memory_free_bytes",
            "cpu_load",
        ):
            val = res[key]
            self.assertTrue(val == "unknown" or isinstance(val, (int, float)))
        self.assertFalse(res["thresholds_applied"])

    def test_resource_unknown_kept_in_assessment(self):
        ra = build_resource_assessment_from_probe(probe_environment_resources())
        self.assertEqual(ra["resource_safety"]["status"], "unknown")
        self.assertIn(
            "resource_unknown_not_treated_as_safe",
            ra["resource_safety"]["rationale_codes"],
        )
        self.assertTrue(ra["observation_only"])

    def test_resource_delta_observation_only(self):
        before = {"disk_free_bytes": 100, "memory_available_bytes": 50}
        after = {"disk_free_bytes": 80, "memory_available_bytes": 40}
        delta = diff_resource_snapshots(before, after)
        self.assertEqual(delta["disk_free_bytes_delta"], -20)
        self.assertIn("観測専用", delta["note"])
        self.assertIn("resource_delta_observation_only", delta["rationale_codes"])


class ExecutionObservationD1aTests(unittest.TestCase):
    def test_duration_and_termination(self):
        begun = begin_execution_observation("exec-test-1")
        facts = finalize_execution_observation(
            begun, returncode=0, timed_out=False
        )
        self.assertEqual(facts["execution_id"], "exec-test-1")
        self.assertIsInstance(facts["duration_seconds"], float)
        self.assertFalse(facts["timed_out"])
        self.assertTrue(facts["process_terminated"])
        self.assertIn("long_running_not_defined_as_dangerous", facts["rationale_codes"])

    def test_execution_id_links_pre_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            eid = new_execution_id()
            pre = build_observation_record(
                execution_id=eid,
                stage="pre",
                resource_before={"disk_free_bytes": 1},
            )
            post = build_observation_record(
                execution_id=eid,
                stage="post",
                resource_before={"disk_free_bytes": 1},
                resource_after={"disk_free_bytes": 2},
                execution_facts=finalize_execution_observation(
                    begin_execution_observation(eid), returncode=0
                ),
            )
            append_observation_log(pre, log_dir=tmp)
            append_observation_log(post, log_dir=tmp)
            rows = load_observation_log(eid, log_dir=tmp)
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["stage"] for r in rows}, {"pre", "post"})
            self.assertTrue(all(r["execution_id"] == eid for r in rows))


class PolicyObservationNoExpandTests(unittest.TestCase):
    def test_observation_does_not_override_gate_deny(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _dangerous())
        self.assertFalse(gate["allow_execute"])
        rich_obs = {
            "git_facts": {
                "in_git_repo": True,
                "targets_covered": True,
                "restore_mechanism_available": True,
            },
            "resource_before": {"disk_free_ratio": 0.9},
        }
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_dangerous(),
            git_facts={
                "git_repo": True,
                "restore_via_git": True,
                "targets_covered": True,
                "tracked_targets": ["a"],
                "all_targets_tracked": True,
                "untracked_targets": [],
            },
            observation=rich_obs,
            resource_assessment=build_resource_assessment_from_probe(
                {"disk_free_ratio": 0.01, "source": "local_probe"}
            ),
        )
        self.assertEqual(tp["allow_execute"], gate["allow_execute"])
        self.assertFalse(tp["allow_execute"])
        self.assertNotEqual(tp["decision"], POLICY_AUTO)
        self.assertFalse(tp["audit"]["observation_affects_allow_execute"])
        self.assertFalse(tp["audit"]["auto_range_expanded"])

    def test_allow_execute_same_as_d0_passthrough(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _safe_limited())
        tp = evaluate_trusted_personal_policy(
            mode=MODE_DEFAULT,
            gate=gate,
            safety=_safe_limited(),
            observation={"resource_before": probe_environment_resources()},
            execution_id="x",
        )
        self.assertEqual(tp["decision"], POLICY_AUTO)
        self.assertEqual(tp["allow_execute"], gate["allow_execute"])

    def test_no_disk_10_percent_or_fixed_thresholds_in_sources(self):
        blobs = [
            inspect.getsource(probe_environment_resources),
            inspect.getsource(build_resource_assessment_from_probe),
            inspect.getsource(evaluate_trusted_personal_policy),
        ]
        joined = "\n".join(blobs)
        self.assertNotIn("0.10", joined)
        self.assertNotIn("10%", joined)
        self.assertIn("no_disk_10_percent_rule", joined)
        self.assertIn("no_fixed_resource_thresholds", joined)

    def test_evaluate_candidate_gate_wires_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = evaluate_candidate_gate(
                {
                    "command": "powershell",
                    "args": [
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Get-CimInstance Win32_OperatingSystem | Select FreePhysicalMemory",
                    ],
                },
                {"available_commands": ["powershell"], "platform": "Windows"},
                verified_environment={
                    "language": "python",
                    "architecture": "AMD64",
                    "platform": "windows",
                },
                skip_llm=True,
                collect_observations=True,
                observation_log_dir=tmp,
            )
            self.assertIn("execution_id", out)
            self.assertIn("git_facts", out)
            self.assertIn("resource_before", out)
            self.assertEqual(out["phase_d"]["phase"], "kss-phase-d1a")
            self.assertFalse(out["phase_d"]["allow_execute_expanded"])
            # Gate deny を観測で覆っていない
            self.assertEqual(
                out["trusted_personal"]["allow_execute"],
                out["gate"]["allow_execute"],
            )
            rows = load_observation_log(out["execution_id"], log_dir=tmp)
            self.assertGreaterEqual(len(rows), 1)
            self.assertEqual(rows[0]["stage"], "pre")


if __name__ == "__main__":
    unittest.main()
