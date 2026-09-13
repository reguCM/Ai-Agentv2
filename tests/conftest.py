"""Root test isolation: do not write operational Mission memory into the repo."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mission_memory_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MISSION_MEMORY_DIR", str(tmp_path / "mission_memory"))
