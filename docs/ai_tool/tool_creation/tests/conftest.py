"""Pytest fixtures for Tool Creation Layer (isolated from repo-root tests/)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOL_CREATION_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_ROOT = TOOL_CREATION_ROOT / "validator"
SPECS_DIR = TOOL_CREATION_ROOT / "specs"
FAILURE_DIR = TOOL_CREATION_ROOT / "failure_cases"
FIXTURES_DIR = TOOL_CREATION_ROOT / "fixtures"
PHASE2_RUN_DIR = (
    Path(__file__).resolve().parents[4]
    / "runs"
    / "ai_tool"
    / "20260828_052931_tool_creation_phase2"
)

# Allow `from validator...` imports
if str(TOOL_CREATION_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION_ROOT))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def tool_creation_root() -> Path:
    return TOOL_CREATION_ROOT


@pytest.fixture(scope="session")
def valid_spec_paths() -> list[Path]:
    return sorted(SPECS_DIR.glob("*.json"))


@pytest.fixture(scope="session")
def failure_case_paths() -> list[Path]:
    return sorted(FAILURE_DIR.glob("fc*.json"))


@pytest.fixture(scope="session")
def gpu_status_spec() -> dict:
    return load_json(SPECS_DIR / "local_get_gpu_status.json")


@pytest.fixture(scope="session")
def cpu_status_spec() -> dict:
    return load_json(SPECS_DIR / "local_cpu_status.json")


@pytest.fixture(scope="session")
def phase2_frozen_run_dir() -> Path:
    return PHASE2_RUN_DIR
