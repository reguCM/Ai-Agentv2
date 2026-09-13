"""Observation Tool v2 draft specification validation — structure only, no production changes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOL_CREATION = REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

V2_SPECS = [
    TOOL_CREATION / "specs" / "get_gpu_status_v2_draft.json",
    TOOL_CREATION / "specs" / "get_gpu_processes_v2_draft.json",
    TOOL_CREATION / "specs" / "cpu_status_v2_draft.json",
    TOOL_CREATION / "specs" / "get_cpu_status_v2_draft.json",
]


@pytest.fixture(params=V2_SPECS, ids=lambda p: p.stem)
def spec_path(request: pytest.FixtureRequest) -> Path:
    return request.param


@pytest.fixture
def spec_dict(spec_path: Path) -> dict:
    return json.loads(spec_path.read_text(encoding="utf-8"))


def test_v2_draft_validates_accept(spec_path: Path) -> None:
    from validator.validate import validate_tool_spec_file

    result = validate_tool_spec_file(spec_path)
    assert result.verdict == "ACCEPT", result.to_dict()


def test_v2_draft_has_observation_semantics(spec_dict: dict) -> None:
    assert "observation_semantics" in spec_dict
    for key in ("observed", "unknown", "unsupported", "unavailable"):
        assert key in spec_dict["observation_semantics"]


def test_v2_draft_has_supported_environment(spec_dict: dict) -> None:
    assert "supported_environment" in spec_dict
    assert spec_dict["supported_environment"]


def test_v2_draft_has_agent_usage(spec_dict: dict) -> None:
    usage = spec_dict.get("agent_usage") or {}
    assert usage.get("use_for")
    assert usage.get("do_not_use_for")


def test_get_gpu_status_v2_output_unchanged_from_v1() -> None:
    v1 = json.loads((TOOL_CREATION / "specs" / "get_gpu_status_legacy_migrated.json").read_text(encoding="utf-8"))
    v2 = json.loads((TOOL_CREATION / "specs" / "get_gpu_status_v2_draft.json").read_text(encoding="utf-8"))
    assert set(v1["output_schema"]["required"]) == set(v2["output_schema"]["required"])


def test_get_gpu_processes_v2_output_unchanged_from_v1() -> None:
    v1 = json.loads((TOOL_CREATION / "specs" / "get_gpu_processes_legacy_migrated.json").read_text(encoding="utf-8"))
    v2 = json.loads((TOOL_CREATION / "specs" / "get_gpu_processes_v2_draft.json").read_text(encoding="utf-8"))
    assert set(v1["output_schema"]["required"]) == set(v2["output_schema"]["required"])


def test_cpu_status_v2_output_unchanged_from_v1() -> None:
    v1 = json.loads((TOOL_CREATION / "specs" / "cpu_status_legacy_migrated.json").read_text(encoding="utf-8"))
    v2 = json.loads((TOOL_CREATION / "specs" / "cpu_status_v2_draft.json").read_text(encoding="utf-8"))
    assert v1["output_schema"] == v2["output_schema"]


def test_get_cpu_status_is_new_tool_draft() -> None:
    spec = json.loads((TOOL_CREATION / "specs" / "get_cpu_status_v2_draft.json").read_text(encoding="utf-8"))
    assert spec["name"] == "get_cpu_status"
    assert spec["tool_status"] == "unavailable"
    assert spec["provider_specific"]["implementation_status"] == "NOT_IMPLEMENTED"
