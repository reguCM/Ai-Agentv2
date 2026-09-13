"""Tests for Human Review → Catalog status update flow (Phase 3)."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.catalog.review import apply_human_review, get_reviewable_tool
from ai_tool.catalog.store import catalog_entries_dir


@pytest.fixture
def catalog_sandbox(tmp_path: Path) -> Path:
    """Isolated catalog/entries copy — does not mutate production entries."""
    src = catalog_entries_dir()
    dest = tmp_path / "entries"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def reviews_log(tmp_path: Path) -> Path:
    return tmp_path / "reviews.jsonl"


@pytest.fixture
def audit_log(tmp_path: Path) -> Path:
    return tmp_path / "audit.jsonl"


def _read_url_entry(catalog_sandbox: Path) -> dict:
    loaded = get_reviewable_tool("local:read_url_text", entries_dir=catalog_sandbox)
    assert loaded is not None
    return loaded


# --- Review ---


def test_unreviewed_tool_can_be_loaded(catalog_sandbox: Path) -> None:
    entry = _read_url_entry(catalog_sandbox)
    assert entry["adoption_status"] == "not_reviewed"
    assert entry["tool_status"] == "unavailable"
    assert entry["experiment_status"] == "experimental"


def test_record_approved(
    catalog_sandbox: Path,
    reviews_log: Path,
    audit_log: Path,
) -> None:
    result = apply_human_review(
        "local:read_url_text",
        "approved",
        reason="ssrf policy reviewed",
        notes="adoption candidate only",
        entries_dir=catalog_sandbox,
        reviews_log=reviews_log,
        audit_log=audit_log,
    )
    assert result.ok is True
    assert result.record is not None
    assert result.record.review_status == "approved"
    assert result.before_status["adoption_status"] == "not_reviewed"
    assert result.after_status["adoption_status"] == "approved"
    assert result.before_status["tool_status"] == "unavailable"
    assert result.after_status["tool_status"] == "unavailable"
    assert result.before_status["experiment_status"] == "experimental"
    assert result.after_status["experiment_status"] == "experimental"
    assert result.agent_available is False
    assert result.discovery_category == "experimental"
    assert result.execution_count == 0

    entry = _read_url_entry(catalog_sandbox)
    assert entry["human_review"]["reviewer"] == "human"
    assert entry["human_review"]["review_status"] == "approved"

    audit_lines = audit_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == 1
    audit_row = json.loads(audit_lines[0])
    assert audit_row["event"] == "human_review_catalog_update"
    assert audit_row["before_adoption_status"] == "not_reviewed"
    assert audit_row["after_adoption_status"] == "approved"
    assert audit_row["review_action"] == "approved"


def test_record_rejected(catalog_sandbox: Path, audit_log: Path) -> None:
    result = apply_human_review(
        "local:workspace_read_text_scoped",
        "rejected",
        reason="allowlist scope too narrow for production",
        entries_dir=catalog_sandbox,
        audit_log=audit_log,
    )
    assert result.ok is True
    assert result.after_status["adoption_status"] == "rejected"
    assert result.after_status["tool_status"] == "unavailable"
    assert result.after_status["experiment_status"] == "experimental"
    assert result.agent_available is False
    assert result.discovery_category == "unavailable"


def test_record_deferred(catalog_sandbox: Path, audit_log: Path) -> None:
    result = apply_human_review(
        "local:read_url_text",
        "deferred",
        reason="need more real_web smoke data",
        entries_dir=catalog_sandbox,
        audit_log=audit_log,
    )
    assert result.ok is True
    assert result.record is not None
    assert result.record.review_status == "deferred"
    assert result.before_status["adoption_status"] == "not_reviewed"
    assert result.after_status["adoption_status"] == "not_reviewed"
    assert result.agent_available is False


def test_rereview_overwrites_adoption_status(catalog_sandbox: Path, audit_log: Path) -> None:
    first = apply_human_review(
        "local:read_url_text",
        "approved",
        entries_dir=catalog_sandbox,
        audit_log=audit_log,
    )
    assert first.ok is True
    second = apply_human_review(
        "local:read_url_text",
        "rejected",
        reason="policy change",
        entries_dir=catalog_sandbox,
        audit_log=audit_log,
    )
    assert second.ok is True
    assert second.before_status["adoption_status"] == "approved"
    assert second.after_status["adoption_status"] == "rejected"
    assert second.agent_available is False


def test_rereview_blocked_when_not_allowed(catalog_sandbox: Path) -> None:
    apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    blocked = apply_human_review(
        "local:read_url_text",
        "rejected",
        entries_dir=catalog_sandbox,
        allow_rereview=False,
    )
    assert blocked.ok is False
    assert blocked.error == "rereview_not_allowed"
    assert _read_url_entry(catalog_sandbox)["adoption_status"] == "approved"


# --- Agent availability ---


def test_approved_registry_read_url_agent_available(catalog_sandbox: Path) -> None:
    """read_url_text は Registry 正本。catalog 承認後も Registry visibility=agent が優先される。"""
    apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=catalog_sandbox)
    tool = adapter.get_tool_descriptor("local:read_url_text")
    assert tool is not None
    assert tool.agent_available is True
    assert tool.discovery_category == "production"
    assert tool.source == "registry/tools.json"


# --- Registry ---


def test_registry_unchanged_by_review(catalog_sandbox: Path) -> None:
    registry_path = Path(__file__).resolve().parents[3] / "registry" / "tools.json"
    before = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    after = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    assert before == after


# --- LLM ---


def _ollama_tools_from_registry() -> list[dict]:
    """Mirror agent.create_ollama_tools without importing agent.py (module side effects)."""
    registry_path = Path(__file__).resolve().parents[3] / "registry" / "tools.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    tools: list[dict] = []
    for tool in registry["tools"]:
        if tool.get("visibility") != "agent":
            continue
        properties = {}
        required: list[str] = []
        for name, parameter in tool.get("input", {}).items():
            param = dict(parameter)
            is_required = bool(param.pop("required", False))
            properties[name] = param
            if is_required:
                required.append(name)
        for name in tool.get("required") or []:
            if name not in required:
                required.append(name)
        parameters: dict = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": parameters,
                },
            }
        )
    return tools


def test_ollama_schema_unchanged_by_review(catalog_sandbox: Path) -> None:
    before = json.dumps(_ollama_tools_from_registry(), sort_keys=True)
    apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    after = json.dumps(_ollama_tools_from_registry(), sort_keys=True)
    assert before == after


# --- Execution safety ---


def test_review_does_not_execute_tools(catalog_sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import ai_tool.experimental.read_url.reader as reader_mod
    import ai_tool.experimental.scoped_read.reader as scoped_mod

    def boom(*a, **k):
        raise AssertionError("tool must not execute during human review")

    monkeypatch.setattr(reader_mod, "read_url_text", boom)
    monkeypatch.setattr(scoped_mod, "workspace_read_text_scoped", boom)
    result = apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    assert result.ok is True
    assert result.execution_count == 0


# --- Determinism ---


def test_discovery_deterministic_after_review(catalog_sandbox: Path) -> None:
    apply_human_review("local:read_url_text", "approved", entries_dir=catalog_sandbox)
    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=catalog_sandbox)
    a = adapter.discover_tools(audit=False)
    b = adapter.discover_tools(audit=False)
    assert [t.to_dict() for t in a.tools] == [t.to_dict() for t in b.tools]


def test_unknown_tool_not_found(catalog_sandbox: Path) -> None:
    result = apply_human_review(
        "local:does_not_exist",
        "approved",
        entries_dir=catalog_sandbox,
    )
    assert result.ok is False
    assert result.error == "tool_not_found_in_catalog"
