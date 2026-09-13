from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AllowlistRoot:
    id: str
    path: Path


@dataclass(frozen=True)
class PathRules:
    reject_parent_segments: bool
    reject_absolute_outside_repo: bool
    reject_symlink_escape: bool
    allow_directories: bool


@dataclass(frozen=True)
class ReadLimits:
    max_bytes: int
    max_lines_default: int
    encoding: str
    encoding_errors: str


@dataclass(frozen=True)
class ScopedReadConfig:
    tool_id: str
    repo_root: Path
    roots: tuple[AllowlistRoot, ...]
    limits: ReadLimits
    path_rules: PathRules
    config_path: Path

    @property
    def resolved_roots(self) -> tuple[tuple[str, Path], ...]:
        root = self.repo_root.resolve()
        return tuple((r.id, (root / r.path).resolve()) for r in self.roots)


def default_allowlist_config_path(repo_root: Path) -> Path:
    return repo_root / "docs" / "ai_tool" / "tool_creation" / "allowed_roots.experimental.json"


def load_scoped_read_config(
    *,
    repo_root: Path,
    config_path: Path | None = None,
) -> ScopedReadConfig:
    path = config_path or default_allowlist_config_path(repo_root)
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    limits_raw = raw.get("limits") or {}
    rules_raw = raw.get("path_rules") or {}
    roots: list[AllowlistRoot] = []
    for entry in raw.get("roots") or []:
        roots.append(
            AllowlistRoot(
                id=str(entry["id"]),
                path=Path(str(entry["path"])),
            )
        )
    if not roots:
        raise ValueError(f"allowlist roots missing in {path}")
    return ScopedReadConfig(
        tool_id=str(raw.get("tool_id") or "local:workspace_read_text_scoped"),
        repo_root=repo_root.resolve(),
        roots=tuple(roots),
        limits=ReadLimits(
            max_bytes=int(limits_raw.get("max_bytes", 65536)),
            max_lines_default=int(limits_raw.get("max_lines_default", 500)),
            encoding=str(limits_raw.get("encoding", "utf-8")),
            encoding_errors=str(limits_raw.get("encoding_errors", "replace")),
        ),
        path_rules=PathRules(
            reject_parent_segments=bool(rules_raw.get("reject_parent_segments", True)),
            reject_absolute_outside_repo=bool(
                rules_raw.get("reject_absolute_outside_repo", True)
            ),
            reject_symlink_escape=bool(rules_raw.get("reject_symlink_escape", True)),
            allow_directories=bool(rules_raw.get("allow_directories", False)),
        ),
        config_path=path.resolve(),
    )
