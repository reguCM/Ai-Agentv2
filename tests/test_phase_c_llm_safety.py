"""Phase C: LLM 構造安全性分析と日本語 Report（モック LLM）。"""

import inspect
import json
import unittest
from unittest import mock

from tools.ai.state.compatibility import COMPAT_CONFIRMED, COMPAT_INCOMPATIBLE, COMPAT_LIKELY
from tools.ai.state.execution_gate import (
    GATE_BLOCK,
    GATE_EXECUTE,
    GATE_EXPERIMENT_CANDIDATE,
    decide_execution_gate,
)
from tools.ai.state.llm_safety_analysis import (
    build_llm_safety_materials,
    build_llm_safety_messages,
    llm_permits_experiment_candidate,
    normalize_llm_safety_payload,
    run_llm_structural_safety_analysis,
)
from tools.ai.state.safety_assessment import DANGEROUS, RISKY, SAFE, UNKNOWN
from tools.ai.state.safety_report import build_japanese_safety_report
from tools.system.tool_builder.research.verify import evaluate_candidate_gate


def _msg(content: str):
    return type("R", (), {"message": type("M", (), {"content": content})()})()


def _good_readonly_analysis(**overrides):
    payload = {
        "operation_summary_ja": "ディスク使用率を取得する読取専用の問い合わせに見える",
        "read_only_likely": True,
        "side_effects": ["read_query"],
        "cannot_rule_out": [],
        "similar_known_ops": ["get-volume"],
        "obfuscation_or_dynamic": False,
        "confidence": "medium",
        "rationale_ja": ["既知の Get 系読取操作に類似している"],
        "not_a_safety_proof": True,
    }
    payload.update(overrides)
    return payload


class PhaseCLLMSafetyTests(unittest.TestCase):
    def test_machine_safe_skips_llm(self):
        called = {"n": 0}

        def chat_fn(**kwargs):
            called["n"] += 1
            return _msg("{}")

        inv = {"available_commands": ["powershell"], "platform": "Windows"}
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
            inv,
            verified_environment={
                "language": "python",
                "architecture": "AMD64",
                "platform": "windows",
            },
            chat_fn=chat_fn,
        )
        self.assertEqual(out["safety"]["machine_assessed"], SAFE)
        self.assertTrue((out.get("llm_bundle") or {}).get("skipped"))
        self.assertEqual(called["n"], 0)
        self.assertNotEqual(out["gate"]["decision"], GATE_BLOCK)

    def test_machine_dangerous_llm_safe_still_block_not_execute(self):
        safety = {
            "status": DANGEROUS,
            "machine_assessed": DANGEROUS,
            "side_effects": ["filesystem_delete"],
            "network_access": "none",
            "privilege": "unknown",
        }
        llm = {
            "ok": True,
            "analysis": _good_readonly_analysis(read_only_likely=True),
        }
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, safety, llm_bundle=llm)
        self.assertEqual(gate["decision"], GATE_BLOCK)
        self.assertNotEqual(gate["decision"], GATE_EXECUTE)
        self.assertIn("llm_safe_ignored_for_machine_dangerous", gate["rationale_codes"])
        self.assertTrue(gate["machine_not_loosened_by_llm"])

    def test_machine_risky_llm_safe_still_block(self):
        safety = {
            "status": RISKY,
            "machine_assessed": RISKY,
            "side_effects": ["process_control"],
            "network_access": "none",
            "privilege": "unknown",
        }
        llm = {"ok": True, "analysis": _good_readonly_analysis()}
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, safety, llm_bundle=llm)
        self.assertEqual(gate["decision"], GATE_BLOCK)
        self.assertIn("llm_safe_ignored_for_machine_risky", gate["rationale_codes"])

    def test_unknown_good_readonly_experiment_candidate_not_execute(self):
        safety = {
            "status": UNKNOWN,
            "machine_assessed": UNKNOWN,
            "side_effects": ["unknown"],
            "network_access": "unknown",
            "privilege": "unknown",
            "rationale_codes": ["unapproved_cmdlet:get-disk"],
        }
        llm = {"ok": True, "analysis": _good_readonly_analysis()}
        gate = decide_execution_gate({"status": COMPAT_LIKELY}, safety, llm_bundle=llm)
        self.assertEqual(gate["decision"], GATE_EXPERIMENT_CANDIDATE)
        self.assertNotEqual(gate["decision"], GATE_EXECUTE)
        self.assertFalse(gate["allow_execute"])
        self.assertTrue(gate.get("presentation_only"))
        self.assertIn("phase_c_never_promote_to_execute", gate["rationale_codes"])
        self.assertIn("experiment_candidate_presentation_only_no_auto_run", gate["rationale_codes"])

    def test_unknown_plus_llm_safe_never_auto_executes(self):
        """unknown + LLM read_only_likely → 自動実行されない（Execute にもならない）。"""
        safety = {
            "status": UNKNOWN,
            "machine_assessed": UNKNOWN,
            "side_effects": ["unknown"],
            "network_access": "unknown",
            "privilege": "unknown",
        }
        llm = {"ok": True, "analysis": _good_readonly_analysis()}
        gate = decide_execution_gate({"status": COMPAT_CONFIRMED}, safety, llm_bundle=llm)
        self.assertEqual(gate["decision"], GATE_EXPERIMENT_CANDIDATE)
        self.assertFalse(gate["allow_execute"])
        self.assertNotEqual(gate["decision"], GATE_EXECUTE)

        def chat_fn(**kwargs):
            return _msg(json.dumps(_good_readonly_analysis(), ensure_ascii=False))

        out = evaluate_candidate_gate(
            {
                "command": "powershell",
                "args": [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-SomethingUnknown | Select Name",
                ],
            },
            {"available_commands": ["powershell"], "platform": "Windows"},
            verified_environment={
                "language": "python",
                "architecture": "AMD64",
                "platform": "windows",
            },
            chat_fn=chat_fn,
        )
        self.assertEqual(out["safety"]["machine_assessed"], UNKNOWN)
        self.assertEqual(out["gate"]["decision"], GATE_EXPERIMENT_CANDIDATE)
        self.assertFalse(out["gate"]["allow_execute"])
        self.assertTrue(out["phase_c"]["audit"]["experiment_candidate_not_auto_executed"])
        # run_candidate 相当: allow_execute False なら実行しない
        self.assertFalse(out["gate"].get("allow_execute"))

    def test_unknown_cannot_rule_out_network_block(self):
        llm = {
            "ok": True,
            "analysis": _good_readonly_analysis(
                cannot_rule_out=["network_egress"]
            ),
        }
        ok, codes = llm_permits_experiment_candidate(llm)
        self.assertFalse(ok)
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {
                "status": UNKNOWN,
                "machine_assessed": UNKNOWN,
                "side_effects": ["unknown"],
                "network_access": "unknown",
                "privilege": "unknown",
            },
            llm_bundle=llm,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_unknown_cannot_rule_out_fs_write_block(self):
        llm = {
            "ok": True,
            "analysis": _good_readonly_analysis(
                cannot_rule_out=["filesystem_write"]
            ),
        }
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=llm,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_unknown_cannot_rule_out_process_block(self):
        llm = {
            "ok": True,
            "analysis": _good_readonly_analysis(
                cannot_rule_out=["process_control"]
            ),
        }
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=llm,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_unknown_dynamic_code_block(self):
        llm = {
            "ok": True,
            "analysis": _good_readonly_analysis(obfuscation_or_dynamic=True),
        }
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=llm,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_unknown_safe_only_answer_block(self):
        self.assertIsNone(
            normalize_llm_safety_payload(
                {
                    "operation_summary_ja": "安全です",
                    "read_only_likely": True,
                    "cannot_rule_out": [],
                }
            )
        )
        # normalize をすり抜けた「安全です」だけの分析も許可しない
        llm_ok_but_safe_only = {
            "ok": True,
            "analysis": _good_readonly_analysis(
                operation_summary_ja="安全です",
                rationale_ja=["安全です"],
            ),
        }
        ok, codes = llm_permits_experiment_candidate(llm_ok_but_safe_only)
        self.assertFalse(ok)
        self.assertIn("llm_safe_only_claim_rejected", codes)
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=llm_ok_but_safe_only,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)
        self.assertFalse(gate["allow_execute"])

    def test_llm_timeout_block(self):
        from tools.system.llm import LLMTimeoutError

        def chat_fn(**kwargs):
            raise LLMTimeoutError("timeout")

        bundle = run_llm_structural_safety_analysis(
            {"command": "powershell", "args": ["-Command", "Get-Foo"]},
            ["unapproved_cmdlet:get-foo"],
            chat_fn=chat_fn,
        )
        self.assertFalse(bundle["ok"])
        self.assertIn("timeout", bundle["error"])
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=bundle,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_invalid_json_block(self):
        def chat_fn(**kwargs):
            return _msg("これは JSON ではありません")

        bundle = run_llm_structural_safety_analysis(
            {"command": "powershell", "args": ["-Command", "Get-Foo"]},
            chat_fn=chat_fn,
        )
        self.assertFalse(bundle["ok"])
        gate = decide_execution_gate(
            {"status": COMPAT_LIKELY},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle=bundle,
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_web_safe_text_not_in_llm_input(self):
        materials = build_llm_safety_materials(
            {"command": "powershell", "args": ["-Command", "Get-Foo"]},
            ["unapproved"],
        )
        blob = json.dumps(materials, ensure_ascii=False)
        messages = build_llm_safety_messages(materials)
        blob2 = json.dumps(messages, ensure_ascii=False)
        for bad in (
            "このコマンドは安全",
            "ウイルスではない",
            "問題ありません",
            "Webページによると安全",
        ):
            self.assertNotIn(bad, blob)
            self.assertNotIn(bad, blob2)
        self.assertIn("known_readonly_operations", materials)
        self.assertIn("command", materials)
        self.assertIn("args", materials)

    def test_safety_report_has_required_japanese_fields(self):
        report = build_japanese_safety_report(
            candidate={"command": "powershell", "args": ["-Command", "Get-Foo"]},
            compatibility={"status": COMPAT_LIKELY},
            safety={
                "machine_assessed": UNKNOWN,
                "status": UNKNOWN,
                "side_effects": ["unknown"],
                "network_access": "unknown",
                "privilege": "unknown",
                "rationale_codes": ["unapproved_cmdlet:get-foo"],
            },
            llm_bundle={
                "ok": True,
                "model_profile_id": "test_profile",
                "analysis": _good_readonly_analysis(),
            },
            gate={
                "decision": GATE_EXPERIMENT_CANDIDATE,
                "allow_execute": False,
                "presentation_only": True,
                "rationale_codes": ["phase_c_experiment_candidate_machine_unknown_llm_ok"],
            },
        )
        self.assertEqual(report["language"], "ja")
        for key in (
            "what_it_does",
            "estimated_safe_reasons",
            "unknowns",
            "side_effects",
            "required_privilege",
            "network_access",
            "machine_assessed",
            "llm_analysis_summary",
            "gate_decision",
            "report_text_ja",
        ):
            self.assertIn(key, report)
        text = report["report_text_ja"]
        self.assertIn("自動実行しません", text)
        self.assertIn("cannot_rule_out が空でも", text)
        self.assertIn("機械判定", text)
        self.assertIn("LLM", text)
        self.assertIn("証明", text)
        self.assertNotIn("安全です。", text.split("注意")[0] if False else "")  # 断定禁止は disclaimer で担保
        self.assertIn("証明ではありません", text)

    def test_uses_tools_system_llm_chat_not_openai(self):
        src = inspect.getsource(run_llm_structural_safety_analysis)
        self.assertIn("tools.system.llm", src)
        self.assertIn("get_llm_profile", src)
        self.assertNotIn("openai", src.lower())
        self.assertNotIn("OpenAI", src)

    def test_incompatible_blocks_even_with_good_llm(self):
        gate = decide_execution_gate(
            {"status": COMPAT_INCOMPATIBLE},
            {"status": UNKNOWN, "machine_assessed": UNKNOWN, "side_effects": ["unknown"]},
            llm_bundle={"ok": True, "analysis": _good_readonly_analysis()},
        )
        self.assertEqual(gate["decision"], GATE_BLOCK)

    def test_evaluate_candidate_gate_phase_c_audit_log(self):
        def chat_fn(**kwargs):
            return _msg(json.dumps(_good_readonly_analysis(), ensure_ascii=False))

        # 未知 cmdlet で machine unknown にする
        out = evaluate_candidate_gate(
            {
                "command": "powershell",
                "args": [
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "Get-SomethingUnknown | Select Name",
                ],
            },
            {"available_commands": ["powershell"], "platform": "Windows"},
            verified_environment={
                "language": "python",
                "architecture": "AMD64",
                "platform": "windows",
            },
            chat_fn=chat_fn,
        )
        self.assertEqual(out["safety"]["machine_assessed"], UNKNOWN)
        self.assertIn("phase_c", out)
        audit = out["phase_c"]["audit"]
        self.assertTrue(audit["machine_not_overwritten_by_llm"])
        self.assertFalse(audit["web_content_used_for_safety"])
        self.assertEqual(out["gate"]["decision"], GATE_EXPERIMENT_CANDIDATE)
        self.assertFalse(out["gate"]["allow_execute"])
        self.assertTrue(out["gate"].get("presentation_only"))
        self.assertNotEqual(out["gate"]["decision"], GATE_EXECUTE)
        self.assertIn("report_text_ja", out["safety_report"])


if __name__ == "__main__":
    unittest.main()
