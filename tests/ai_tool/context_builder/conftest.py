"""Pytest fixtures for Tool Development Context Builder."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def selection_rules(repo_root: Path) -> dict:
    path = repo_root / "docs" / "ai_tool" / "context_builder" / "selection_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))
