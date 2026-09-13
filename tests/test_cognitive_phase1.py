"""Phase 1 Cognitive State: generate / update / visualize — no Selector or Tools."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.ai.state.cognitive_fingerprint import KNOWN_FEATURE_KEYS, build_fingerprint_candidate
from tools.ai.state.cognitive_session import compare_snapshots, load_session, save_session
from tools.ai.state.cognitive_state import (
    add_claim,
    add_evidence,
    add_hypothesis,
    add_unresolved,
    confirm_human_review,
    init_from_user_request,
    render_cognitive_markdown,
    set_intent,
    sync_unresolved_from_task_state,
)
from tools.ai.state.task_state import TaskState


class CognitivePhase1Tests(unittest.TestCase):
    def test_init_update_render_and_persist(self):
        state = init_from_user_request("diagnose search_web handoff", source="test")
        set_intent(state, "understand stdout vs llm path", reason_code="test")
        add_hypothesis(state, "json.dumps truncates tool result", reason_code="test")
        add_unresolved(state, "Is ranking the cause?", reason_code="test")
        add_claim(state, "path includes agent messages append", reason_code="test")
        add_evidence(state, "code read of agent.py tool append", kind="code", reason_code="test")

        md = render_cognitive_markdown(state)
        self.assertIn("Cognitive State (Phase 1)", md)
        self.assertIn("diagnose search_web handoff", md)
        self.assertFalse(state["meta"]["selector_invoked"])
        self.assertFalse(state["meta"]["tool_execution_invoked"])
        self.assertFalse(state["meta"]["auto_fix_allowed"])
        self.assertTrue(state["confidence"]["do_not_use_as_selector_signal"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = save_session(state, root=root)
            self.assertTrue((path / "state.json").is_file())
            self.assertTrue((path / "COGNITIVE_STATE.md").is_file())
            self.assertTrue((path / "fingerprint_candidate.json").is_file())
            self.assertTrue((path / "audit_full.json").is_file())

            loaded = load_session(state["session_id"], root=root)
            self.assertEqual(loaded["goal"], state["goal"])
            fp = json.loads((path / "fingerprint_candidate.json").read_text(encoding="utf-8"))
            self.assertFalse(fp["selector"]["invoked"])
            self.assertEqual(fp["kind"], "task_fingerprint_candidate")
            for key in KNOWN_FEATURE_KEYS:
                self.assertIn(key, fp["features"])

    def test_sync_from_task_state(self):
        state = init_from_user_request("task", source="test")
        ts = TaskState(
            task="task",
            open_questions=[{"id": "oq1", "text": "Where is filter applied?", "status": "open"}],
        )
        n = sync_unresolved_from_task_state(state, ts)
        self.assertEqual(n, 1)
        self.assertEqual(state["unresolved_questions"][0]["text"], "Where is filter applied?")
        self.assertTrue(state["links"]["open_questions_synced"])
        # idempotent on same text
        self.assertEqual(sync_unresolved_from_task_state(state, ts), 0)

    def test_fingerprint_does_not_import_selector(self):
        import sys

        banned = [k for k in sys.modules if "diagnostic_framework.selector" in k]
        state = init_from_user_request("code path and ranking filter logs", source="test")
        add_unresolved(state, "handoff?", reason_code="t")
        add_unresolved(state, "ranking?", reason_code="t")
        add_unresolved(state, "caller?", reason_code="t")
        fp = build_fingerprint_candidate(state, feature_overrides={"code_available": True})
        self.assertTrue(fp["features"]["code_available"])
        self.assertEqual(fp["uncertainty"]["level"], "high")
        self.assertFalse(fp["selector"]["invoked"])
        banned_after = [k for k in sys.modules if "diagnostic_framework.selector" in k]
        self.assertEqual(banned, banned_after)

    def test_human_confirm_and_compare(self):
        before = init_from_user_request("g", source="test")
        after = init_from_user_request("g", source="test")
        after["session_id"] = before["session_id"]
        set_intent(after, "new intent", reason_code="t")
        confirm_human_review(after, reviewer="tester")
        self.assertEqual(after["human_review"]["status"], "confirmed")
        diff = compare_snapshots(before, after)
        self.assertIn("intent", diff["changed_keys"])


if __name__ == "__main__":
    unittest.main()
