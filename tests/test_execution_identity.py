"""CURSOR_VALIDATION: execution_identity unit tests (not Project Agent capability)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.system import execution_identity as ei


class ExecutionIdentityTests(unittest.TestCase):
    def test_digest_stable_and_bounded(self):
        payload = {"a": "x" * 2000}
        digest = ei.digest_result(payload, max_chars=50)
        self.assertEqual(digest["type"], "dict")
        self.assertEqual(len(digest["sha256_16"]), 16)
        self.assertTrue(digest["preview"].endswith("…"))
        self.assertLessEqual(len(digest["preview"]), 51)

    def test_record_separates_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "id.jsonl"
            with mock.patch.dict(os.environ, {"AI_AGENT_EXECUTION_LOG": str(log)}):
                ei.log_run_start(
                    execution_actor=ei.PROJECT_AGENT,
                    entrypoint="agent.py",
                    llm="qwen3:8b",
                    extra={"event": "agent_start"},
                )
                ei.log_run_start(
                    execution_actor=ei.RESEARCH_PIPELINE,
                    entrypoint="research.llm_benchmarks.research_implement",
                    llm="qwen3:8b",
                    extra={"event": "pipeline_start"},
                )
            rows = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(rows[0]["execution_actor"], "PROJECT_AGENT")
            self.assertEqual(rows[0]["event"], "agent_start")
            self.assertEqual(rows[0]["entrypoint"], "agent.py")
            self.assertEqual(rows[1]["execution_actor"], "RESEARCH_PIPELINE")
            self.assertEqual(rows[1]["event"], "pipeline_start")


import os  # noqa: E402  used in test after import ei


if __name__ == "__main__":
    unittest.main()
