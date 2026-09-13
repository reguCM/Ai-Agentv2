"""S9 — runtime_bridge routing and persistence (mocked safety stack)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_safety.runtime_bridge import (
    bridge_test_execution,
    build_llm_tool_summary,
    persist_explicit_run_packet,
    safety_run_closure_predicate,
)

FAKE_OUTCOME = {
    "executor_called": True,
    "test_failed": False,
    "run_closed": True,
    "resolution": {"resolution_result": "EXECUTED", "action_id": "A1"},
    "runner_evidence": {"run_closed": True, "closure_reason": "normal"},
}


def test_predicate_satisfied():
    assert safety_run_closure_predicate(FAKE_OUTCOME) is True


def test_predicate_fails_when_test_failed():
    bad = {**FAKE_OUTCOME, "test_failed": True}
    assert safety_run_closure_predicate(bad) is False


def test_build_llm_summary_truncates_and_fields():
    outcome = {
        **FAKE_OUTCOME,
        "runner_evidence": {
            **FAKE_OUTCOME["runner_evidence"],
            "execution_result": {"ok": True, "returncode": 0, "stdout_tail": "x" * 2000},
        },
        "persisted_run_path": "/tmp/r.json",
    }
    summary = build_llm_tool_summary(outcome)
    assert summary["executor_called"] is True
    assert len(summary["stdout_tail"]) <= 1500


def test_persist_explicit_run_packet(tmp_path: Path):
    path = persist_explicit_run_packet(FAKE_OUTCOME, action_id="A9", runs_dir=tmp_path)
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["executor_called"] is True


def test_bridge_test_execution_persists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from test_safety import runtime_bridge as mod

    def _fake(**_kwargs):
        return dict(FAKE_OUTCOME)

    monkeypatch.setattr(mod, "run_explicit_test_with_auto_resolution", _fake)
    out = bridge_test_execution(
        action_id="A-bridge",
        test_plan={"plan_id": "p", "commands": ["echo"], "declared_primary_risk_level": "LEVEL_1", "declared_dimensions": {}},
        persist=True,
        runs_dir=tmp_path,
    )
    assert "persisted_run_path" in out
    assert Path(out["persisted_run_path"]).is_file()
