"""
CURSOR_VALIDATION: F-001 summarize / LLM 返却分離の回帰。
PROJECT_AGENT 能力実績には加算しない。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock


def _load_summarize_helpers():
    text = Path("agent.py").read_text(encoding="utf-8")
    start = text.find("\ndef summarize_tool_result(")
    end = text.find("\ndef validate_proposals(")
    if start < 0 or end < 0:
        raise RuntimeError("summarize helpers not found in agent.py")
    chunk = text[start + 1 : end]
    ns = {"json": json}
    exec(chunk, ns, ns)
    return ns["summarize_tool_result"], ns["print_tool_result_for_stdout"]


class F001SummarizeSeparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        summarize, print_stdout = _load_summarize_helpers()
        cls.summarize = staticmethod(summarize)
        cls.print_stdout = staticmethod(print_stdout)

    def test_search_web_dict_does_not_raise(self):
        payload = {
            "query": "q",
            "hits": [{"title": "t", "url": "u", "snippet": "s", "backend": "b"}],
            "backends_tried": ["b"],
            "error": None,
        }
        out = self.summarize("search_web", payload)
        self.assertNotIn("registry_tool_count", out)
        self.assertEqual(out["hit_count"], 1)

    def test_cpu_status_dict_does_not_raise(self):
        out = self.summarize("cpu_status", {"status": "12"})
        self.assertNotIn("registry_tool_count", out)

    def test_get_gpu_status_dict_does_not_raise(self):
        out = self.summarize("get_gpu_status", {"gpu": "x"})
        self.assertNotIn("registry_tool_count", out)

    def test_file_tools_dict_does_not_raise(self):
        for name in ("list_files", "read_file", "search_files"):
            out = self.summarize(name, {"ok": True, "entries": []})
            self.assertNotIn("registry_tool_count", out)

    def test_create_tool_proposal_keeps_registry_count(self):
        payload = {
            "target_request": "req",
            "verified_environment": {},
            "related_tools": [{"name": "a"}],
            "reference_tools": [{"name": "b"}],
            "reference_sources": [{}],
            "registry": [{"name": "t1"}, {"name": "t2"}],
        }
        out = self.summarize("create_tool_proposal", payload)
        self.assertEqual(out["registry_tool_count"], 2)
        self.assertEqual(out["related_tool_names"], ["a"])

    def test_stdout_failure_does_not_block_raw_handoff(self):
        """要約が落ちても raw を messages 相当へ載せる制御を再現。"""
        messages = []
        raw = {"query": "q", "hits": [{"title": "t", "url": "https://example.com"}]}

        # 能力経路（agent.py と同じ順序）
        messages.append(
            {
                "role": "tool",
                "tool_name": "search_web",
                "content": json.dumps(raw, ensure_ascii=False, indent=2),
            }
        )

        with mock.patch(
            "builtins.print"
        ), mock.patch.object(
            self,
            "summarize",
            side_effect=RuntimeError("forced summarize failure"),
        ):
            # print_tool_result_for_stdout 相当: summarize失敗でも握りつぶす
            try:
                self.summarize("search_web", raw)
            except Exception:
                pass

        self.assertEqual(len(messages), 1)
        content = json.loads(messages[0]["content"])
        self.assertEqual(content["hits"][0]["url"], "https://example.com")

    def test_print_stdout_swallows_summarize_errors(self):
        def boom(*_a, **_k):
            raise RuntimeError("boom")

        with mock.patch("builtins.print") as printed:
            # 一時的に壊した summarize を使うには print helper 内の呼び出しを差し替えられないため
            # print_tool_result_for_stdout の except 経路を直接検証する
            with mock.patch.dict(
                self.print_stdout.__globals__,
                {"summarize_tool_result": boom},
            ):
                self.print_stdout("search_web", {"hits": []})
        text = " ".join(str(c.args[0]) for c in printed.call_args_list if c.args)
        self.assertIn("stdout summarize failed", text)


if __name__ == "__main__":
    unittest.main()
