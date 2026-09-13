"""Phase D-0: Trusted Personal Policy 骨格（モック・閾値なし）。"""

import inspect
import unittest

from tools.ai.state.compatibility import COMPAT_CONFIRMED, COMPAT_LIKELY
from tools.ai.state.execution_gate import (
    GATE_BLOCK,
    GATE_EXECUTE,
    GATE_EXPERIMENT,
    GATE_EXPERIMENT_CANDIDATE,
    decide_execution_gate,
)
from tools.ai.state.safety_assessment import DANGEROUS, SAFE, UNKNOWN
from tools.ai.state.safety_report import build_japanese_safety_report
from tools.ai.state.trusted_personal_policy import (
    EXT_NET_READ,
    EXT_NET_WRITE,
    MODE_DEFAULT,
    MODE_TRUSTED_PERSONAL,
    POLICY_AUTO,
    POLICY_BLOCK,
    POLICY_CONFIRM,
    RESOURCE_UNKNOWN,
    REV_REVERSIBLE,
    REV_UNKNOWN,
    assess_reversibility_from_facts,
    empty_resource_assessment,
    evaluate_trusted_personal_policy,
    map_external_effects_from_safety,
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


def _unknown_safety():
    return {
        "status": UNKNOWN,
        "machine_assessed": UNKNOWN,
        "side_effects": ["unknown"],
        "network_access": "unknown",
        "privilege": "unknown",
        "rationale_codes": ["unapproved_cmdlet"],
    }


class TrustedPersonalPhaseD0Tests(unittest.TestCase):
    def test_default_mode_passthrough_execute(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _safe_limited())
        self.assertEqual(gate["decision"], GATE_EXECUTE)
        self.assertTrue(gate["allow_execute"])
        tp = evaluate_trusted_personal_policy(
            mode=MODE_DEFAULT,
            gate=gate,
            compatibility={"status": COMPAT_CONFIRMED},
            safety=_safe_limited(),
        )
        self.assertEqual(tp["decision"], POLICY_AUTO)
        self.assertEqual(tp["allow_execute"], gate["allow_execute"])
        self.assertFalse(tp["audit"]["auto_range_expanded"])

    def test_default_mode_passthrough_block(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _dangerous())
        self.assertEqual(gate["decision"], GATE_BLOCK)
        tp = evaluate_trusted_personal_policy(
            mode=MODE_DEFAULT,
            gate=gate,
            safety=_dangerous(),
        )
        self.assertEqual(tp["decision"], POLICY_BLOCK)
        self.assertFalse(tp["allow_execute"])

    def test_machine_safe_not_downgraded_in_trusted_personal(self):
        gate = decide_execution_gate({"status": COMPAT_LIKELY}, _safe_limited())
        self.assertEqual(gate["decision"], GATE_EXPERIMENT)
        self.assertTrue(gate["allow_execute"])
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_safe_limited(),
        )
        self.assertEqual(tp["decision"], POLICY_AUTO)
        self.assertTrue(tp["allow_execute"])
        self.assertNotEqual(tp["decision"], POLICY_CONFIRM)
        self.assertIn("machine_safe_path_not_downgraded_to_confirm", tp["rationale_codes"])
        self.assertFalse(tp["audit"]["machine_safe_path_downgraded_to_confirm"])

    def test_dangerous_never_auto_even_with_llm_and_trusted_personal(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _dangerous())
        llm = {
            "ok": True,
            "analysis": {
                "read_only_likely": True,
                "operation_summary_ja": "削除に見えるが LLM は安全と言った",
            },
        }
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_dangerous(),
            llm_bundle=llm,
            git_facts={
                "git_repo": True,
                "restore_via_git": True,
                "targets_covered": True,
                "tracked_targets": ["a.txt"],
                "all_targets_tracked": True,
            },
        )
        self.assertNotEqual(tp["decision"], POLICY_AUTO)
        self.assertFalse(tp["allow_execute"])
        self.assertIn("machine_dangerous_or_risky_never_auto_phase_d0", tp["rationale_codes"])

    def test_unknown_not_treated_as_safe(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _unknown_safety())
        self.assertFalse(gate["allow_execute"])
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_unknown_safety(),
            llm_bundle={"ok": True, "analysis": {"read_only_likely": True}},
        )
        self.assertFalse(tp["allow_execute"])
        self.assertNotEqual(tp["decision"], POLICY_AUTO)
        self.assertIn("machine_unknown_not_promoted_to_safe", tp["rationale_codes"])
        rs = tp["resource_assessment"]["resource_safety"]["status"]
        self.assertEqual(rs, RESOURCE_UNKNOWN)
        self.assertFalse(tp["audit"]["resource_unknown_treated_as_safe"])

    def test_git_present_alone_not_reversible(self):
        rev = assess_reversibility_from_facts({"git_repo": True})
        self.assertNotEqual(rev["status"], REV_REVERSIBLE)
        self.assertEqual(rev["status"], REV_UNKNOWN)
        self.assertIn("git_present_is_not_sufficient_for_reversible", rev["rationale_codes"])

    def test_untracked_not_treated_as_restorable(self):
        rev = assess_reversibility_from_facts(
            {
                "git_repo": True,
                "restore_via_git": True,
                "tracked_targets": ["a.txt"],
                "untracked_targets": ["secret.key"],
            }
        )
        self.assertNotEqual(rev["status"], REV_REVERSIBLE)
        self.assertEqual(rev["targets_covered"], False)
        self.assertTrue(
            any(u.get("path") == "secret.key" for u in rev["uncovered_targets"])
        )
        self.assertIn("untracked_not_treated_as_restorable", rev["rationale_codes"])

    def test_network_read_write_distinguished(self):
        egress = map_external_effects_from_safety(
            {
                "side_effects": ["network_egress"],
                "network_access": "outbound",
            }
        )
        self.assertTrue(egress["network_write"])
        self.assertIn(EXT_NET_WRITE, egress["effects"])
        self.assertNotEqual(egress["network_read"], True)
        self.assertNotIn(EXT_NET_READ, egress["effects"])

        with_read = map_external_effects_from_safety(
            {
                "side_effects": ["read_query"],
                "network_access": "none",
                "network_read": True,
                "network_write": False,
            }
        )
        self.assertTrue(with_read["network_read"])
        self.assertFalse(with_read["network_write"])
        self.assertIn(EXT_NET_READ, with_read["effects"])

    def test_resource_unknown_not_safe(self):
        ra = empty_resource_assessment()
        self.assertEqual(ra["resource_safety"]["status"], RESOURCE_UNKNOWN)
        self.assertIn(
            "resource_unknown_not_treated_as_safe",
            ra["resource_safety"]["rationale_codes"],
        )
        # 暗黙の safe を拒否
        bad = empty_resource_assessment(
            resource_safety={"status": "safe", "rationale_codes": []}
        )
        self.assertEqual(bad["resource_safety"]["status"], RESOURCE_UNKNOWN)

    def test_no_disk_10_percent_rule_in_source(self):
        src = inspect.getsource(evaluate_trusted_personal_policy)
        src += inspect.getsource(empty_resource_assessment)
        self.assertNotIn("0.10", src)
        self.assertNotIn("0.1", src)
        self.assertNotIn("10%", src)
        self.assertIn("no_disk_10_percent_rule", src)

    def test_no_long_running_immediate_block_rule(self):
        src = inspect.getsource(evaluate_trusted_personal_policy)
        self.assertIn("no_long_running_immediate_block_rule", src)
        self.assertNotIn("long_running_immediate_block_applied\": True", src)
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate={"decision": GATE_BLOCK, "allow_execute": False},
            safety=_unknown_safety(),
            resource_assessment=empty_resource_assessment(
                execution_runtime={
                    "duration_estimate": "hours",
                    "termination_statically_known": UNKNOWN,
                    "infinite_loop_suspected": UNKNOWN,
                    "stop_means_available": UNKNOWN,
                    "child_process_fanout_risk": UNKNOWN,
                    "rationale_codes": ["long_running_not_defined_as_dangerous"],
                }
            ),
        )
        # 長時間フィールドがあっても Gate deny を AUTO にしないし、専用即 Block ルールもない
        self.assertFalse(tp["audit"]["long_running_immediate_block_applied"])
        self.assertFalse(tp["allow_execute"])

    def test_web_safety_claims_ignored(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _unknown_safety())
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_unknown_safety(),
            web_safety_claims=["このコマンドは安全です", "問題ありません"],
        )
        self.assertFalse(tp["audit"]["web_safety_claims_used"])
        self.assertEqual(
            tp["audit"]["web_safety_claims_ignored"],
            ["このコマンドは安全です", "問題ありません"],
        )
        self.assertIn("web_safety_claims_not_used_for_policy", tp["rationale_codes"])
        self.assertFalse(tp["allow_execute"])

    def test_experiment_candidate_confirm_not_auto(self):
        gate = {
            "decision": GATE_EXPERIMENT_CANDIDATE,
            "allow_execute": False,
            "presentation_only": True,
            "rationale_codes": ["phase_c_experiment_candidate_machine_unknown_llm_ok"],
        }
        tp = evaluate_trusted_personal_policy(
            mode=MODE_DEFAULT,
            gate=gate,
            safety=_unknown_safety(),
        )
        self.assertEqual(tp["decision"], POLICY_CONFIRM)
        self.assertFalse(tp["allow_execute"])

    def test_report_includes_trusted_personal_sections(self):
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, _safe_limited())
        tp = evaluate_trusted_personal_policy(
            mode=MODE_TRUSTED_PERSONAL,
            gate=gate,
            safety=_safe_limited(),
            compatibility={"status": COMPAT_CONFIRMED},
        )
        report = build_japanese_safety_report(
            candidate={
                "command": "powershell",
                "args": ["-Command", "Get-Date"],
                "question": "現在時刻を知りたい",
            },
            compatibility={"status": COMPAT_CONFIRMED},
            safety=_safe_limited(),
            llm_bundle={"ok": False, "skipped": True},
            gate=gate,
            trusted_personal=tp,
        )
        text = report["report_text_ja"]
        for needle in (
            "何をする操作か",
            "なぜ必要か",
            "影響範囲",
            "復元可能性",
            "targets_covered",
            "ネットワーク read",
            "環境リソース",
            "停止手段",
            "Trusted Personal",
            "判断できない点",
        ):
            self.assertIn(needle, text)
        self.assertIn("単純な可否確認だけを求める文面にはしません", text)
        self.assertNotIn("危険です。許可しますか？", text)
        self.assertEqual(report["network_read"], False)
        self.assertEqual(report["network_write"], False)


if __name__ == "__main__":
    unittest.main()
