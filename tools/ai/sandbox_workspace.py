"""Safe Development Workspace primitives for a runtime-owned sandbox.

Session creation may materialize a dedicated Git worktree. Runtime file mutation
is deliberately absent; future tools must use :func:`resolve_sandbox_path`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import hashlib
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
from typing import Callable, Mapping
from uuid import uuid4
import json


SANDBOX_PARENT_ENV = "AI_AGENT_SANDBOX_PARENT"
SANDBOX_WORKSPACE_CONFIG = "config/sandbox_workspace.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sandbox_workspace_config_path(repo_root: Path | str | None = None) -> Path:
    root = Path(__file__).resolve().parents[2] if repo_root is None else Path(repo_root)
    return root / SANDBOX_WORKSPACE_CONFIG


def resolve_configured_sandbox_parent(
    development_worktree: Path | str | None = None,
    *,
    config_path: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve Dedicated Sandbox parent from env or config, not path arithmetic."""
    env = os.environ if environ is None else environ
    override = str(env.get(SANDBOX_PARENT_ENV) or "").strip()
    if override:
        return Path(override).expanduser().resolve(strict=False)

    path = sandbox_workspace_config_path() if config_path is None else Path(config_path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SandboxIdentityError(
            f"sandbox workspace config unreadable: {path}: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SandboxIdentityError("sandbox workspace config must be an object")
    parent = str(data.get("sandbox_parent") or "").strip()
    if not parent:
        raise SandboxIdentityError("sandbox workspace config missing sandbox_parent")

    configured = Path(parent)
    if configured.is_absolute():
        return configured.resolve(strict=False)

    relative_to = str(data.get("relative_to") or "volume_root").strip()
    if relative_to != "volume_root":
        raise SandboxIdentityError(
            f"unsupported sandbox_parent relative_to: {relative_to}"
        )
    if development_worktree is None:
        development_worktree = Path(__file__).resolve().parents[2]
    volume_root = Path(development_worktree).resolve(strict=False).anchor
    return (Path(volume_root) / parent).resolve(strict=False)


class SandboxError(RuntimeError):
    """Base error for a sandbox that cannot safely be used."""


class SandboxPathError(SandboxError, ValueError):
    """A requested path is not contained by the sandbox root."""


class SandboxIdentityError(SandboxError):
    """The live Git worktree identity differs from the recorded identity."""


@dataclass(frozen=True)
class GitWorkspaceIdentity:
    root: Path
    branch: str
    head: str
    production_root: Path


@dataclass(frozen=True)
class SandboxSession:
    session_id: str
    sandbox_root: str
    branch: str
    base_head: str
    current_head: str
    status: str
    created_at: str
    production_applied: bool = False
    git_base: str | None = None
    workspace_base: str | None = None
    session_kind: str = "WORKTREE"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


IdentityReader = Callable[[Path], GitWorkspaceIdentity]


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def read_git_identity(root: Path) -> GitWorkspaceIdentity:
    """Read the linked-worktree identity without modifying Git state."""
    requested = root.resolve(strict=True)
    actual_root = Path(_git(requested, "rev-parse", "--show-toplevel")).resolve()
    branch = _git(actual_root, "branch", "--show-current")
    head = _git(actual_root, "rev-parse", "HEAD")
    common_dir_text = _git(actual_root, "rev-parse", "--git-common-dir")
    common_dir = Path(common_dir_text)
    if not common_dir.is_absolute():
        common_dir = actual_root / common_dir
    common_dir = common_dir.resolve()
    production_root = common_dir.parent if common_dir.name.casefold() == ".git" else actual_root
    return GitWorkspaceIdentity(actual_root, branch, head, production_root.resolve())


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def create_sandbox_session(
    sandbox_root: Path | str,
    *,
    expected_branch: str | None = None,
    expected_base_head: str | None = None,
    identity_reader: IdentityReader = read_git_identity,
) -> SandboxSession:
    """Create a runtime identity from observed state, not from LLM-provided IDs."""
    identity = identity_reader(Path(sandbox_root))
    if _is_within(identity.root, identity.production_root):
        raise SandboxIdentityError("sandbox root must be separate from production root")
    if expected_branch is not None and identity.branch != expected_branch:
        raise SandboxIdentityError(
            f"sandbox branch mismatch: expected {expected_branch}, observed {identity.branch}"
        )
    if expected_base_head is not None and identity.head != expected_base_head:
        raise SandboxIdentityError("sandbox base HEAD does not match the observed HEAD")
    return SandboxSession(
        session_id=f"sandbox-{uuid4()}",
        sandbox_root=str(identity.root),
        branch=identity.branch,
        base_head=identity.head,
        current_head=identity.head,
        status="ACTIVE",
        created_at=_now(),
        production_applied=False,
        git_base=f"HEAD:{identity.head}",
        workspace_base=f"HEAD:{identity.head}",
        session_kind="WORKTREE",
    )


def _listed_paths(root: Path, *args: str) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in _git_bytes(root, *args, "-z").split(b"\0")
        if item
    ]


def _safe_member(root: Path, relative: str) -> tuple[Path, tuple[str, ...]]:
    windows_path = PureWindowsPath(relative)
    if (
        not relative
        or Path(relative).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in windows_path.parts
    ):
        raise SandboxPathError(f"unsafe workspace member: {relative}")
    parts = tuple(windows_path.parts)
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve(strict=False)
    if not _is_within(resolved, root.resolve(strict=True)):
        raise SandboxPathError(f"workspace member escapes root: {relative}")
    return candidate, parts


def _copy_workspace_state(source: Path, destination: Path) -> str:
    """Overlay tracked and non-ignored untracked files, preserving working state."""
    tracked = _listed_paths(source, "ls-files")
    untracked = _listed_paths(source, "ls-files", "--others", "--exclude-standard")
    digest = hashlib.sha256()
    for kind, relative in [("tracked", item) for item in tracked] + [
        ("untracked", item) for item in untracked
    ]:
        source_path, parts = _safe_member(source, relative)
        target_path, _ = _safe_member(destination, relative)
        digest.update(kind.encode("ascii") + b"\0" + relative.encode("utf-8") + b"\0")
        if not source_path.exists() and not source_path.is_symlink():
            digest.update(b"deleted\0")
            if target_path.is_dir() and not target_path.is_symlink():
                shutil.rmtree(target_path)
            elif target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            continue
        source_resolved = source_path.resolve(strict=True)
        if not _is_within(source_resolved, source.resolve(strict=True)):
            raise SandboxPathError(f"source symlink escapes workspace: {relative}")
        if source_path.is_dir():
            # Git paths are files; an inaccessible directory is not a safe snapshot input.
            raise SandboxPathError(f"workspace member is not a file: {relative}")
        data = source_path.read_bytes()
        digest.update(data)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(data)
        try:
            shutil.copystat(source_path, target_path, follow_symlinks=False)
        except OSError:
            pass
    return digest.hexdigest()


def _remove_worktree(source: Path, sandbox_root: Path, branch: str) -> None:
    subprocess.run(
        [
            "git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
            "worktree", "remove", "--force", str(sandbox_root),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
            "branch", "-D", branch,
        ],
        check=True,
        capture_output=True,
    )


def create_dedicated_sandbox_session(
    source_worktree: Path | str,
    sandbox_parent: Path | str,
) -> SandboxSession:
    """Create a unique linked worktree and overlay the current workspace state.

    The UUID, root and branch are selected here by trusted Runtime code. The source
    worktree is checked before and after creation and is never written.
    """
    source = Path(source_worktree).resolve(strict=True)
    source_identity = read_git_identity(source)
    parent = Path(sandbox_parent).resolve(strict=False)
    if _is_within(parent, source_identity.production_root) or _is_within(
        parent, source_identity.root
    ):
        raise SandboxIdentityError("dedicated sandbox parent must be outside development and production roots")
    token = str(uuid4())
    session_id = f"S-{token}"
    sandbox_root = parent / session_id
    branch = f"agent-sandbox/{session_id}"
    if sandbox_root.exists():
        raise SandboxIdentityError("dedicated sandbox root already exists")
    before = _git_bytes(source, "status", "--porcelain=v1", "-z")
    created = False
    try:
        parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [
                    "git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source),
                    # The Workspace snapshot below is authoritative and copies
                    # both HEAD files and current unstaged/untracked state.
                    # Avoid Git's Windows checkout here: deeply nested tracked
                    # research paths can exceed MAX_PATH before that safe
                    # snapshot overlay gets a chance to run.
                    "worktree", "add", "--no-checkout", "-b", branch,
                    str(sandbox_root), source_identity.head,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise SandboxIdentityError(
                f"git worktree add failed: {stderr or 'no stderr'}"
            ) from exc
        created = True
        workspace_hash = _copy_workspace_state(source, sandbox_root)
        observed = read_git_identity(sandbox_root)
        if observed.branch != branch or observed.head != source_identity.head:
            raise SandboxIdentityError("created sandbox identity does not match requested base")
        source_after = read_git_identity(source)
        if (
            source_after.root != source_identity.root
            or source_after.branch != source_identity.branch
            or source_after.head != source_identity.head
        ):
            raise SandboxIdentityError("source worktree identity changed during sandbox creation")
        if _git_bytes(source, "status", "--porcelain=v1", "-z") != before:
            raise SandboxIdentityError("source workspace changed during sandbox creation")
        session = SandboxSession(
            session_id=session_id,
            sandbox_root=str(sandbox_root.resolve(strict=True)),
            branch=branch,
            base_head=source_identity.head,
            current_head=source_identity.head,
            status="ACTIVE",
            created_at=_now(),
            production_applied=False,
            git_base=f"HEAD:{source_identity.head}",
            workspace_base=f"working-tree-sha256:{workspace_hash}",
            session_kind="DEDICATED",
        )
        verify_sandbox_identity(session)
        return session
    except Exception:
        if created:
            try:
                _remove_worktree(source, sandbox_root, branch)
            except Exception as cleanup_error:
                raise SandboxIdentityError(
                    f"sandbox creation failed and cleanup also failed: {cleanup_error}"
                )
        elif sandbox_root.exists():
            shutil.rmtree(sandbox_root)
        raise


def discard_dedicated_sandbox_session(
    session: SandboxSession,
    source_worktree: Path | str,
) -> None:
    """Discard only the recorded dedicated worktree; never touch source files."""
    source = Path(source_worktree).resolve(strict=True)
    verify_sandbox_identity(session)
    sandbox_root = Path(session.sandbox_root).resolve(strict=True)
    if sandbox_root == source or _is_within(sandbox_root, source):
        raise SandboxIdentityError("refusing to discard the development worktree")
    _remove_worktree(source, sandbox_root, session.branch)


def verify_sandbox_identity(
    session: SandboxSession,
    *,
    identity_reader: IdentityReader = read_git_identity,
) -> GitWorkspaceIdentity:
    """Fail closed when the recorded sandbox is no longer the active worktree."""
    if session.status != "ACTIVE" or session.production_applied:
        raise SandboxIdentityError("sandbox session is not active and isolated")
    identity = identity_reader(Path(session.sandbox_root))
    expected_root = Path(session.sandbox_root).resolve(strict=True)
    if identity.root != expected_root:
        raise SandboxIdentityError("sandbox root identity changed")
    if identity.branch != session.branch:
        raise SandboxIdentityError("sandbox branch identity changed")
    if identity.head != session.current_head:
        raise SandboxIdentityError("sandbox HEAD identity changed")
    if _is_within(identity.root, identity.production_root):
        raise SandboxIdentityError("sandbox is not separated from production")
    return identity


def resolve_sandbox_path(
    session: SandboxSession,
    relative_path: str | os.PathLike[str],
    *,
    must_exist: bool = False,
    identity_reader: IdentityReader = read_git_identity,
) -> Path:
    """Resolve a relative path and reject lexical or filesystem escapes."""
    identity = verify_sandbox_identity(session, identity_reader=identity_reader)
    raw = os.fspath(relative_path)
    windows_path = PureWindowsPath(raw)
    native_path = Path(raw)
    if not raw or native_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise SandboxPathError("sandbox paths must be relative")
    parts = PureWindowsPath(raw.replace("/", "\\")).parts
    if ".." in parts:
        raise SandboxPathError("parent traversal is not allowed")
    root = identity.root.resolve(strict=True)
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except (FileNotFoundError, OSError) as exc:
        raise SandboxPathError(f"sandbox path cannot be resolved: {raw}") from exc
    # resolve() follows existing symlinks and Windows junction/reparse points.
    if not _is_within(resolved, root):
        raise SandboxPathError("resolved path escapes sandbox root")
    return resolved


def sandbox_status_ja(session: SandboxSession) -> dict[str, object]:
    """Return a deterministic, user-facing Japanese status payload."""
    return {
        "実行環境": "Sandbox",
        "現在の状態": session.status,
        "Session ID": session.session_id,
        "Sandbox Root": session.sandbox_root,
        "Branch": session.branch,
        "Base HEAD": session.base_head,
        "Current HEAD": session.current_head,
        "本番反映": "本番にはまだ反映されていません",
        "production_applied": session.production_applied,
        "Git Base": session.git_base,
        "Workspace Base": session.workspace_base,
        "Session Kind": session.session_kind,
    }


__all__ = [
    "GitWorkspaceIdentity",
    "SandboxError",
    "SandboxIdentityError",
    "SandboxPathError",
    "SandboxSession",
    "create_sandbox_session",
    "create_dedicated_sandbox_session",
    "discard_dedicated_sandbox_session",
    "read_git_identity",
    "resolve_configured_sandbox_parent",
    "resolve_sandbox_path",
    "sandbox_status_ja",
    "verify_sandbox_identity",
]
