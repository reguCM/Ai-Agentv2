from dataclasses import replace
import os
from pathlib import Path
import subprocess

import pytest

import tools.ai.sandbox_workspace as sandbox_workspace
from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
from tools.ai.sandbox_workspace import (
    GitWorkspaceIdentity,
    SandboxIdentityError,
    SandboxPathError,
    create_dedicated_sandbox_session,
    create_sandbox_session,
    discard_dedicated_sandbox_session,
    resolve_sandbox_path,
    verify_sandbox_identity,
)
from tools.ai.task_runtime import AgentTaskRuntime


def identity_reader(sandbox: Path, production: Path, *, branch: str = "feature", head: str = "a" * 40):
    sandbox = sandbox.resolve()
    production = production.resolve()

    def read(_root: Path) -> GitWorkspaceIdentity:
        return GitWorkspaceIdentity(sandbox, branch, head, production)

    return read


def session(tmp_path: Path):
    root = tmp_path / "sandbox"
    production = tmp_path / "production"
    root.mkdir()
    production.mkdir()
    reader = identity_reader(root, production)
    return create_sandbox_session(root, identity_reader=reader), reader, root


def test_sandbox_session_is_runtime_observed_and_production_is_false(tmp_path):
    item, reader, root = session(tmp_path)
    assert item.session_id.startswith("sandbox-")
    assert item.sandbox_root == str(root.resolve())
    assert item.branch == "feature"
    assert item.base_head == item.current_head == "a" * 40
    assert item.status == "ACTIVE"
    assert item.production_applied is False
    assert verify_sandbox_identity(item, identity_reader=reader).root == root.resolve()


def test_relative_path_inside_sandbox_is_accepted(tmp_path):
    item, reader, root = session(tmp_path)
    target = root / "docs" / "contract.md"
    target.parent.mkdir()
    target.write_text("contract", encoding="utf-8")
    assert resolve_sandbox_path(item, "docs/contract.md", must_exist=True, identity_reader=reader) == target.resolve()


@pytest.mark.parametrize("path", ["../outside.txt", "docs/../../outside.txt"])
def test_parent_escape_is_rejected(tmp_path, path):
    item, reader, _root = session(tmp_path)
    with pytest.raises(SandboxPathError, match="parent traversal"):
        resolve_sandbox_path(item, path, identity_reader=reader)


@pytest.mark.parametrize("path", ["C:\\Users\\person\\secret.txt", "D:/outside.txt", "\\\\server\\share\\x"])
def test_windows_absolute_paths_are_rejected(tmp_path, path):
    item, reader, _root = session(tmp_path)
    with pytest.raises(SandboxPathError, match="relative"):
        resolve_sandbox_path(item, path, identity_reader=reader)


def test_native_absolute_path_is_rejected(tmp_path):
    item, reader, _root = session(tmp_path)
    with pytest.raises(SandboxPathError, match="relative"):
        resolve_sandbox_path(item, str(tmp_path.resolve()), identity_reader=reader)


def test_symlink_or_junction_escape_is_rejected(tmp_path):
    item, reader, root = session(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink/junction creation is unavailable: {exc}")
    with pytest.raises(SandboxPathError, match="escapes"):
        resolve_sandbox_path(item, "escape/file.txt", identity_reader=reader)


def test_identity_mismatch_stops_use(tmp_path):
    item, _reader, root = session(tmp_path)
    changed = identity_reader(root, tmp_path / "production", branch="other")
    with pytest.raises(SandboxIdentityError, match="branch"):
        verify_sandbox_identity(item, identity_reader=changed)


def test_production_root_cannot_be_used_as_sandbox(tmp_path):
    root = tmp_path / "production"
    root.mkdir()
    reader = identity_reader(root, root)
    with pytest.raises(SandboxIdentityError, match="separate"):
        create_sandbox_session(root, identity_reader=reader)


def test_runtime_owns_session_and_snapshot_exposes_japanese_status(tmp_path, monkeypatch):
    item, reader, _root = session(tmp_path)
    monkeypatch.setattr("tools.ai.task_runtime.verify_sandbox_identity", lambda value: reader(Path(value.sandbox_root)))
    orchestrator = ChatTaskOrchestrator("r", "repository audit", sandbox_session=item)
    orchestrator.initialize()
    snapshot = orchestrator.snapshot()
    assert snapshot["sandbox_session"]["session_id"] == item.session_id
    assert snapshot["sandbox_status_ja"]["実行環境"] == "Sandbox"
    assert snapshot["sandbox_status_ja"]["production_applied"] is False


def test_inactive_or_applied_session_is_rejected(tmp_path):
    item, reader, _root = session(tmp_path)
    with pytest.raises(SandboxIdentityError, match="not active"):
        verify_sandbox_identity(replace(item, status="CLOSED"), identity_reader=reader)
    with pytest.raises(SandboxIdentityError, match="isolated"):
        verify_sandbox_identity(replace(item, production_applied=True), identity_reader=reader)


def test_runtime_has_no_production_mutation_api():
    forbidden = {"edit_file", "create_file", "apply_to_production", "promote"}
    assert forbidden.isdisjoint(set(dir(AgentTaskRuntime)))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _dirty_source(tmp_path: Path) -> Path:
    source = tmp_path / "development"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.name", "Sandbox Test")
    _git(source, "config", "user.email", "sandbox@example.invalid")
    (source / "tracked.txt").write_text("git base\n", encoding="utf-8")
    (source / "deleted.txt").write_text("remove me\n", encoding="utf-8")
    _git(source, "add", "tracked.txt", "deleted.txt")
    _git(source, "commit", "-m", "base")
    (source / "tracked.txt").write_text("workspace base\n", encoding="utf-8")
    (source / "deleted.txt").unlink()
    (source / "new_runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
    return source


def test_dedicated_session_copies_current_workspace_without_touching_source(tmp_path):
    source = _dirty_source(tmp_path)
    before_status = _git(source, "status", "--porcelain=v1")
    before_head = _git(source, "rev-parse", "HEAD")
    item = create_dedicated_sandbox_session(source, tmp_path / "sandboxes")
    sandbox = Path(item.sandbox_root)
    try:
        assert sandbox != source.resolve()
        assert sandbox.parent == (tmp_path / "sandboxes").resolve()
        assert (sandbox / "tracked.txt").read_text(encoding="utf-8") == "workspace base\n"
        assert not (sandbox / "deleted.txt").exists()
        assert (sandbox / "new_runtime.py").read_text(encoding="utf-8") == "VALUE = 1\n"
        assert item.branch.startswith("agent-sandbox/S-")
        assert item.base_head == item.current_head == before_head
        assert item.git_base == f"HEAD:{before_head}"
        assert item.workspace_base.startswith("working-tree-sha256:")
        assert item.production_applied is False
        assert _git(source, "status", "--porcelain=v1") == before_status
        assert _git(source, "rev-parse", "HEAD") == before_head
    finally:
        discard_dedicated_sandbox_session(item, source)


def test_sandbox_changes_and_discard_do_not_affect_development_worktree(tmp_path):
    source = _dirty_source(tmp_path)
    before_status = _git(source, "status", "--porcelain=v1")
    item = create_dedicated_sandbox_session(source, tmp_path / "sandboxes")
    sandbox = Path(item.sandbox_root)
    (sandbox / "tracked.txt").write_text("sandbox-only\n", encoding="utf-8")
    assert (source / "tracked.txt").read_text(encoding="utf-8") == "workspace base\n"
    discard_dedicated_sandbox_session(item, source)
    assert not sandbox.exists()
    assert (source / "tracked.txt").read_text(encoding="utf-8") == "workspace base\n"
    assert _git(source, "status", "--porcelain=v1") == before_status


def test_path_guard_uses_new_dedicated_root(tmp_path):
    source = _dirty_source(tmp_path)
    item = create_dedicated_sandbox_session(source, tmp_path / "sandboxes")
    try:
        resolved = resolve_sandbox_path(item, "tracked.txt", must_exist=True)
        assert resolved.parent == Path(item.sandbox_root)
        with pytest.raises(SandboxPathError):
            resolve_sandbox_path(item, "../development/tracked.txt")
    finally:
        discard_dedicated_sandbox_session(item, source)


def test_runtime_creates_and_owns_dedicated_session(tmp_path):
    source = _dirty_source(tmp_path)
    runtime = AgentTaskRuntime("runtime")
    item = runtime.start_dedicated_sandbox(source, tmp_path / "sandboxes")
    try:
        assert runtime.sandbox_session == item
        assert runtime.sandbox_identity()["session_id"] == item.session_id
        with pytest.raises(ValueError, match="already owns"):
            runtime.start_dedicated_sandbox(source, tmp_path / "other")
    finally:
        discard_dedicated_sandbox_session(item, source)


def test_dedicated_sandbox_parent_cannot_be_development_tree(tmp_path):
    source = _dirty_source(tmp_path)
    before = _git(source, "status", "--porcelain=v1")
    with pytest.raises(SandboxIdentityError, match="outside"):
        create_dedicated_sandbox_session(source, source / ".agent-sandboxes")
    assert _git(source, "status", "--porcelain=v1") == before


def test_creation_failure_cleans_only_dedicated_worktree(tmp_path, monkeypatch):
    source = _dirty_source(tmp_path)
    before = _git(source, "status", "--porcelain=v1")
    parent = tmp_path / "sandboxes"

    def fail_copy(_source, _destination):
        raise SandboxPathError("unsafe snapshot")

    monkeypatch.setattr(sandbox_workspace, "_copy_workspace_state", fail_copy)
    with pytest.raises(SandboxPathError, match="unsafe snapshot"):
        create_dedicated_sandbox_session(source, parent)
    assert _git(source, "status", "--porcelain=v1") == before
    assert not list(parent.glob("S-*"))
    assert "agent-sandbox/" not in _git(source, "branch", "--list", "agent-sandbox/*")
