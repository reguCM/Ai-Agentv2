from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
from dataclasses import replace

import pytest

import ai_tool.chat_interface.agent_turn as agent_turn
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.sandbox_workspace import (
    create_dedicated_sandbox_session,
    discard_dedicated_sandbox_session,
)
from tools.system.tool_contract import get_registry_tool, registry_entry_to_ollama_parameters
from tools.system.tool_result_contract import validate_tool_result_v1


create_module = importlib.import_module("tools.file.sandbox.create_file")
edit_module = importlib.import_module("tools.file.sandbox.edit_file")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


@pytest.fixture(scope="module")
def dedicated(tmp_path_factory):
    base = tmp_path_factory.mktemp("p218")
    source = base / "development"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Mutation Test")
    _git(source, "config", "user.email", "mutation@example.invalid")
    (source / "existing.txt").write_text("alpha beta gamma\n", encoding="utf-8")
    (source / "duplicate.txt").write_text("same same\n", encoding="utf-8")
    (source / "binary.bin").write_bytes(b"\x00\x01")
    (source / "invalid.bin").write_bytes(b"\xff\xfe")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    before = _git(source, "status", "--porcelain=v1")
    item = create_dedicated_sandbox_session(source, base / "sandboxes")
    yield item, source, before
    discard_dedicated_sandbox_session(item, source)


def assert_v1(result):
    assert validate_tool_result_v1(result) == []


def test_create_file_success_in_dedicated_sandbox(dedicated):
    session, source, _before = dedicated
    result = create_module.create_file("generated/new.txt", "hello\n", sandbox_session=session)
    assert_v1(result)
    assert result["status"] == "success"
    assert result["mutation"]["before_hash"] is None
    assert result["mutation"]["changed"] is True
    assert (Path(session.sandbox_root) / "generated" / "new.txt").read_text(encoding="utf-8") == "hello\n"
    assert not (source / "generated" / "new.txt").exists()


def test_create_rejects_existing_file(dedicated):
    session, _source, _before = dedicated
    result = create_module.create_file("existing.txt", "overwrite", sandbox_session=session)
    assert_v1(result)
    assert result["error"]["code"] == "path_exists"


@pytest.mark.parametrize("path", ["../outside.txt", "C:\\outside.txt", "D:/outside.txt"])
def test_create_rejects_escape_and_absolute_paths(dedicated, path):
    session, source, _before = dedicated
    result = create_module.create_file(path, "bad", sandbox_session=session)
    assert_v1(result)
    assert result["status"] == "failure"
    assert not (source.parent / "outside.txt").exists()


def test_create_requires_runtime_owned_session():
    result = create_module.create_file("x.txt", "x")
    assert_v1(result)
    assert result["error"]["code"] == "sandbox_session_required"


def test_mutation_rejects_non_dedicated_worktree_session(dedicated):
    session, _source, _before = dedicated
    legacy = replace(session, session_kind="WORKTREE")
    created = create_module.create_file("legacy-create.txt", "x", sandbox_session=legacy)
    edited = edit_module.edit_file("existing.txt", "alpha", "x", sandbox_session=legacy)
    assert created["error"]["code"] == "dedicated_sandbox_required"
    assert edited["error"]["code"] == "dedicated_sandbox_required"
    assert not (Path(session.sandbox_root) / "legacy-create.txt").exists()


def test_edit_replaces_exactly_once_and_records_hashes(dedicated):
    session, source, before_status = dedicated
    result = edit_module.edit_file("existing.txt", "beta", "changed", sandbox_session=session)
    assert_v1(result)
    assert result["status"] == "success"
    assert result["mutation"]["before_hash"] != result["mutation"]["after_hash"]
    assert (Path(session.sandbox_root) / "existing.txt").read_text(encoding="utf-8") == "alpha changed gamma\n"
    assert (source / "existing.txt").read_text(encoding="utf-8") == "alpha beta gamma\n"
    assert _git(source, "status", "--porcelain=v1") == before_status


@pytest.mark.parametrize(
    ("path", "old_text", "new_text", "code"),
    [
        ("existing.txt", "missing", "x", "old_text_not_found"),
        ("duplicate.txt", "same", "x", "old_text_not_unique"),
        ("existing.txt", "", "x", "invalid_old_text"),
        ("existing.txt", None, "x", "invalid_old_text"),
        ("existing.txt", "alpha", None, "invalid_new_text"),
        ("", "alpha", "x", "invalid_path"),
        ("binary.bin", "x", "y", "binary_file"),
        ("invalid.bin", "x", "y", "decode_failed"),
    ],
)
def test_edit_rejects_invalid_or_ambiguous_inputs(dedicated, path, old_text, new_text, code):
    session, _source, _before = dedicated
    result = edit_module.edit_file(path, old_text, new_text, sandbox_session=session)
    assert_v1(result)
    assert result["error"]["code"] == code


@pytest.mark.parametrize("path", ["../existing.txt", "C:\\outside.txt", "D:/outside.txt"])
def test_edit_rejects_escape_and_absolute_paths(dedicated, path):
    session, source, _before = dedicated
    result = edit_module.edit_file(path, "alpha", "bad", sandbox_session=session)
    assert_v1(result)
    assert result["status"] == "failure"
    assert (source / "existing.txt").read_text(encoding="utf-8") == "alpha beta gamma\n"


def test_symlink_or_junction_escape_is_rejected_by_mutation_tools(dedicated):
    session, source, _before = dedicated
    outside = source.parent / "outside"
    outside.mkdir(exist_ok=True)
    link = Path(session.sandbox_root) / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink/junction creation is unavailable: {exc}")
    result = create_module.create_file("escape/new.txt", "bad", sandbox_session=session)
    assert_v1(result)
    assert result["status"] == "failure"
    assert not (outside / "new.txt").exists()


def test_registry_schema_exposes_only_llm_arguments():
    for name, required in (
        ("create_file", {"path", "content"}),
        ("edit_file", {"path", "old_text", "new_text"}),
    ):
        entry = get_registry_tool(name, reload=True)
        schema = registry_entry_to_ollama_parameters(entry)
        assert entry["visibility"] == "agent"
        assert set(schema["required"]) == required
        assert "sandbox_session" not in schema["properties"]
        assert entry["security"]["production_write"] is False


def test_mutation_is_observed_evidence_but_does_not_complete_task(dedicated, monkeypatch):
    session, _source, _before = dedicated
    monkeypatch.setattr("tools.ai.task_runtime.verify_sandbox_identity", lambda _item: None)
    orchestrator = ChatTaskOrchestrator(
        "mutation-runtime",
        "create a sandbox file",
        completion_conditions=["implementation is verified by tests"],
        sandbox_session=session,
    )
    orchestrator.initialize()
    result = create_module.create_file("runtime-record.txt", "record", sandbox_session=session)
    orchestrator.observe_tool(
        "create_file",
        {"path": "runtime-record.txt", "content": "record"},
        result,
        {"path": "runtime-record.txt"},
        relevant_tools=["create_file"],
        raw_result=result,
    )
    evidence_id = orchestrator.record_sandbox_mutation(result)
    assert evidence_id is not None
    evidence = orchestrator.runtime.evidence[evidence_id]
    assert evidence.certainty == "OBSERVED"
    assert evidence.supported_completion_conditions == []
    assert orchestrator.runtime.tasks["T1"].status != "complete"
    assert orchestrator.runtime.mutations[0].sandbox_session_id == session.session_id


def test_no_mutation_tool_can_target_development_or_production(dedicated):
    session, source, before_status = dedicated
    source_bytes = (source / "existing.txt").read_bytes()
    for path in (str(source / "existing.txt"), "../development/existing.txt"):
        assert create_module.create_file(path, "bad", sandbox_session=session)["ok"] is False
        assert edit_module.edit_file(path, "alpha", "bad", sandbox_session=session)["ok"] is False
    assert (source / "existing.txt").read_bytes() == source_bytes
    assert _git(source, "status", "--porcelain=v1") == before_status


def test_agent_executor_injects_runtime_session_not_llm_arguments(dedicated, tmp_path, monkeypatch):
    session, _source, _before = dedicated
    monkeypatch.setattr(
        agent_turn,
        "authorize_tool_execution",
        lambda *_args, **_kwargs: {"allowed": True, "decision": "allow"},
    )
    monkeypatch.setattr(agent_turn, "log_tool_call", lambda **_kwargs: None)
    monkeypatch.setattr(agent_turn, "log_tool_result", lambda **_kwargs: None)
    result = agent_turn._execute_agent_tool(
        "create_file",
        {"path": "executor-created.txt", "content": "safe"},
        trust_path=tmp_path / "trust.json",
        sandbox_session=session,
    )
    assert_v1(result)
    assert result["mutation"]["sandbox_session_id"] == session.session_id
    denied = agent_turn._execute_agent_tool(
        "create_file",
        {"path": "without-session.txt", "content": "unsafe"},
        trust_path=tmp_path / "trust.json",
    )
    assert_v1(denied)
    assert denied["error"]["code"] == "sandbox_session_required"
