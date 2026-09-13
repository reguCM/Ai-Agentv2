from __future__ import annotations

import json

import pytest

from ai_tool.context_builder.builder import build_tool_development_context
from ai_tool.context_builder.models import P0_SLOTS
from ai_tool.context_builder.sensitive import is_sensitive_path


@pytest.mark.parametrize(
    "tool_id",
    [
        "local:workspace_read_text_scoped",
        "local:get_gpu_status",
        "local:cpu_status",
    ],
)
def test_normal_context_generation(repo_root, tool_id: str) -> None:
    result = build_tool_development_context(
        tool_id,
        repo_root=repo_root,
        fetch_content=True,
        compression="full",
        audit=False,
    )
    assert result.status in ("OK", "PARTIAL")
    assert result.tool_id.startswith("local:")
    assert result.manifest.tool_id == result.tool_id
    assert result.manifest.slots["identity"]["status"] == "FOUND"
    assert result.manifest.slots["specification"]["status"] == "FOUND"
    assert len(result.selected_files) >= 5
    assert result.manifest.slots["identity"]["data"]["name"]


def test_scoped_read_integration_fetches_allowlisted(repo_root) -> None:
    result = build_tool_development_context(
        "local:workspace_read_text_scoped",
        repo_root=repo_root,
        fetch_content=True,
        audit=False,
    )
    spec_path = "docs/ai_tool/tool_creation/specs/local_workspace_read_text_scoped.json"
    assert spec_path in result.content
    assert "workspace_read_text_scoped" in result.content[spec_path]


def test_fixed_slot_classification(repo_root) -> None:
    result = build_tool_development_context(
        "local:get_gpu_status",
        repo_root=repo_root,
        fetch_content=False,
        compression="none",
        audit=False,
    )
    slots = result.manifest.slots
    assert slots["contract"]["status"] == "FOUND"
    assert slots["implementation"]["status"] == "REFERENCE_ONLY"
    assert "tools/system/gpu/gpu_status.py" in slots["implementation"]["files"][0]


def test_missing_tool_id(repo_root) -> None:
    result = build_tool_development_context(
        "local:nonexistent_tool_xyz",
        repo_root=repo_root,
        fetch_content=False,
        audit=False,
    )
    assert result.status == "ERROR"
    assert result.missing_slots == list(P0_SLOTS)


def test_no_sensitive_files_in_selection(repo_root) -> None:
    result = build_tool_development_context(
        "local:get_gpu_status",
        repo_root=repo_root,
        fetch_content=True,
        audit=False,
    )
    for f in result.selected_files:
        assert not is_sensitive_path(f.path)
    for ex in result.excluded_files:
        assert ex["reason"] in ("EXCLUDED_OUTSIDE_ALLOWLIST", "EXCLUDED_SENSITIVE")


def test_allowlist_outside_not_fetched(repo_root) -> None:
    result = build_tool_development_context(
        "local:get_gpu_status",
        repo_root=repo_root,
        fetch_content=True,
        audit=False,
    )
    impl = "tools/system/gpu/gpu_status.py"
    assert impl not in result.content
    impl_entries = [f for f in result.selected_files if impl in f.path]
    assert impl_entries
    assert impl_entries[0].content_status == "EXCLUDED_OUTSIDE_ALLOWLIST"


def test_env_path_excluded_by_rules(repo_root, selection_rules) -> None:
    result = build_tool_development_context(
        "local:workspace_read_text_scoped",
        repo_root=repo_root,
        fetch_content=False,
        audit=False,
    )
    assert not any(".env" in f.path for f in result.selected_files)


def test_deterministic_manifest(repo_root) -> None:
    a = build_tool_development_context(
        "local:cpu_status",
        repo_root=repo_root,
        fetch_content=False,
        compression="none",
        audit=False,
    )
    b = build_tool_development_context(
        "local:cpu_status",
        repo_root=repo_root,
        fetch_content=False,
        compression="none",
        audit=False,
    )
    assert json.dumps(a.manifest.to_dict(), sort_keys=True) == json.dumps(
        b.manifest.to_dict(), sort_keys=True
    )
    paths_a = [f.path for f in a.selected_files]
    paths_b = [f.path for f in b.selected_files]
    assert paths_a == paths_b


def test_unknown_not_fabricated(repo_root) -> None:
    result = build_tool_development_context(
        "local:cpu_status",
        repo_root=repo_root,
        fetch_content=False,
        audit=False,
    )
    tests = result.manifest.slots["tests"]
    assert tests["status"] in ("FOUND", "REFERENCE_ONLY", "UNKNOWN")
    if tests["status"] == "UNKNOWN":
        assert tests.get("reason") == "NOT_FOUND"
        assert "fabricated" not in str(tests)


def test_compression_none_skips_content(repo_root) -> None:
    result = build_tool_development_context(
        "local:workspace_read_text_scoped",
        repo_root=repo_root,
        fetch_content=True,
        compression="none",
        audit=False,
    )
    assert result.content == {}


def test_audit_fields_present(repo_root) -> None:
    result = build_tool_development_context(
        "local:workspace_read_text_scoped",
        repo_root=repo_root,
        fetch_content=False,
        audit=False,
    )
    for f in result.selected_files:
        assert f.slot
        assert f.reason
        assert f.priority in ("P0", "P1", "P2")
