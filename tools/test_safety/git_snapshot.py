"""Read-only git worktree snapshot for test safety postflight."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def git_worktree_snapshot(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    safe = str(root).replace("\\", "/")

    def run(*args: str) -> str | None:
        try:
            proc = subprocess.run(
                ["git", "-c", f"safe.directory={safe}", *args],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
                timeout=30,
            )
            return (proc.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            return None

    porcelain = run("status", "--porcelain") or ""
    return {
        "branch": run("branch", "--show-current"),
        "head": run("rev-parse", "HEAD"),
        "status_short": run("status", "-sb"),
        "porcelain": porcelain,
        "porcelain_lines": _porcelain_lines(porcelain),
    }


def _porcelain_lines(porcelain: str) -> list[str]:
    return [line for line in porcelain.splitlines() if line.strip()]


def porcelain_paths(lines: list[str]) -> set[str]:
    paths: set[str] = set()
    for line in lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            paths.add(path.replace("\\", "/"))
    return paths
