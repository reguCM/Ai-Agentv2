"""
CURSOR_VALIDATION: PROJECT_AGENT Tool Gate（Research Safety 非統合）。
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.system import agent_tool_gate as gate


class AgentToolGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trust = Path(self.tmp.name) / "trust.json"
        self.env = mock.patch.dict(
            os.environ,
            {
                "AI_AGENT_TOOL_TRUST": str(self.trust),
                "AI_AGENT_TOOL_GATE": "confirm",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_default_requires_confirm(self):
        self.assertEqual(
            gate.decide_policy("search_web"),
            gate.POLICY_REQUIRE_CONFIRM,
        )

    def test_deny_when_ask_returns_no(self):
        auth = gate.authorize_tool_execution(
            "search_web",
            {"query": "x"},
            ask_confirm=lambda n, a: "n",
            store_path=self.trust,
        )
        self.assertFalse(auth["allowed"])
        self.assertEqual(auth["decision"], gate.DECISION_DENY)

    def test_allow_once_does_not_promote(self):
        auth = gate.authorize_tool_execution(
            "cpu_status",
            {},
            ask_confirm=lambda n, a: "y",
            store_path=self.trust,
        )
        self.assertTrue(auth["allowed"])
        self.assertFalse(auth["promoted"])
        self.assertFalse(gate.is_auto_allowed("cpu_status", store=gate.load_trust_store(self.trust)))

    def test_always_promotes_then_auto_allows(self):
        auth = gate.authorize_tool_execution(
            "list_files",
            {"path": "."},
            ask_confirm=lambda n, a: "always",
            store_path=self.trust,
        )
        self.assertTrue(auth["allowed"])
        self.assertTrue(auth["promoted"])
        self.assertEqual(
            gate.decide_policy("list_files", store=gate.load_trust_store(self.trust)),
            gate.POLICY_AUTO_ALLOW,
        )
        # 2回目は ask されずに許可
        auth2 = gate.authorize_tool_execution(
            "list_files",
            {"path": "."},
            ask_confirm=lambda n, a: (_ for _ in ()).throw(AssertionError("should not ask")),
            store_path=self.trust,
        )
        self.assertTrue(auth2["allowed"])
        self.assertEqual(auth2.get("source"), "auto_allow_list")

    def test_demote_returns_to_confirm(self):
        gate.promote_tool("read_file", note="test", path=self.trust)
        gate.demote_tool("read_file", note="problem", path=self.trust)
        self.assertEqual(
            gate.decide_policy("read_file", store=gate.load_trust_store(self.trust)),
            gate.POLICY_REQUIRE_CONFIRM,
        )
        store = gate.load_trust_store(self.trust)
        actions = [h.get("action") for h in store.get("history") or []]
        self.assertIn("promote", actions)
        self.assertIn("demote", actions)

    def test_non_tty_none_reply_denies(self):
        auth = gate.authorize_tool_execution(
            "search_web",
            {},
            ask_confirm=lambda n, a: None,
            store_path=self.trust,
        )
        self.assertFalse(auth["allowed"])

    def test_gate_off_skips_confirm(self):
        with mock.patch.dict(os.environ, {"AI_AGENT_TOOL_GATE": "off"}):
            auth = gate.authorize_tool_execution(
                "search_web",
                {},
                ask_confirm=lambda n, a: (_ for _ in ()).throw(AssertionError("no ask")),
                store_path=self.trust,
            )
        self.assertTrue(auth["allowed"])
        self.assertEqual(auth["decision"], "gate_off")

    def test_does_not_import_research_execution_gate(self):
        import tools.system.agent_tool_gate as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from tools.ai.state", source)
        self.assertNotIn("import tools.ai.state", source)
        # 実行時に Research Gate を呼ばない（名前の言及は docstring のみ可）
        self.assertNotIn("decide_execution_gate(", source)
        self.assertNotIn("evaluate_trusted_personal_policy", source)

    def test_cli_promote_demote(self):
        code = gate.main(["promote", "get_gpu_status", "--note", "ok"])
        self.assertEqual(code, 0)
        store = json.loads(self.trust.read_text(encoding="utf-8"))
        self.assertIn("get_gpu_status", store["auto_allow"])
        code = gate.main(["demote", "get_gpu_status"])
        self.assertEqual(code, 0)
        store = json.loads(self.trust.read_text(encoding="utf-8"))
        self.assertNotIn("get_gpu_status", store["auto_allow"])


if __name__ == "__main__":
    unittest.main()
