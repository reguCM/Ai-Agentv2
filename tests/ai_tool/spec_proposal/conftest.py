"""spec_proposal テストが本番 Session / Case を汚さない。"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_case_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_EXECUTION_CASES_DIR", str(tmp_path / "execution_cases"))
    monkeypatch.setenv("AI_AGENT_MISSION_MEMORY_DIR", str(tmp_path / "mission_memory"))
    monkeypatch.setattr("ai_tool.chat_interface.chat_session.SESSIONS_DIR", tmp_path / "sessions")
