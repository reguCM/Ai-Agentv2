"""Tests for storage policy."""
from __future__ import annotations

from pathlib import Path

from ai_tool.experimental.ur_program_validator.storage_policy import (
    format_approval_request,
    probe_storage,
    resolve_storage_root,
)


def test_resolve_storage_root_prefers_d_when_available():
    root = resolve_storage_root(Path("D:/AI-Agent"))
    assert str(root).upper().startswith("D:")


def test_probe_storage_records_c_and_d():
    report = probe_storage(Path("D:/AI-Agent"))
    letters = {d.letter for d in report.drives if d.exists}
    assert "C" in letters
    assert "D" in letters
    assert report.storage_root


def test_docker_move_requires_approval():
    report = probe_storage()
    approval = format_approval_request(report)
    assert approval["requires_approval"] is True
    cats = [i["category"] for i in approval["items"]]
    assert any("Docker Desktop WSL" in c for c in cats)
