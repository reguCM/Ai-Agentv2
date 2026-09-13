"""実験専用 Tool。本番 Registry / 既存実験 Tool には接続しない。"""

from __future__ import annotations

import copy
import fnmatch
import json
import shutil
import subprocess
from pathlib import Path

from research.llm_benchmarks.tool_calling_compression_experiment.execute import (
    run_program,
    run_test,
)


FIXTURE_SRC = Path(__file__).resolve().parent / "fixtures" / "ticket_stage"
TOOL_RESULT_CHAR_LIMIT = 3500

OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "glob": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search text in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string"},
                    "glob": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Write a text file in the working directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_test",
            "description": "Run the project tests.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_program",
            "description": "Run python main.py.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def copy_fixture(dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        FIXTURE_SRC,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
    )
    return dest


def git_init_workspace(workspace: Path):
    subprocess.run(["git", "init"], cwd=str(workspace), check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(workspace), check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=experiment@localhost",
            "-c",
            "user.name=experiment",
            "commit",
            "-m",
            "initial",
        ],
        cwd=str(workspace),
        check=True,
        capture_output=True,
    )


def git_diff(workspace: Path):
    if not (workspace / ".git").exists():
        return ""
    completed = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def resolve_in_workspace(workspace: Path, path):
    raw = "." if path in (None, "") else str(path).strip()
    if ".." in Path(raw).parts:
        return {"ok": False, "error": "path に '..' は使用できません", "path": raw}
    candidate = Path(raw)
    root = workspace.resolve()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return {"ok": False, "error": "作業ディレクトリ外です", "path": raw}
    return resolved


def _rel(workspace: Path, path: Path):
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def read_file(workspace: Path, path, offset=None, limit=None):
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    if not target.exists() or not target.is_file():
        return {"ok": False, "error": "ファイルが存在しません", "path": str(path)}
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    start = 1 if offset is None else int(offset)
    if start < 1:
        return {"ok": False, "error": "offset は 1 以上である必要があります"}
    selected = lines[start - 1 :]
    if limit is not None:
        selected = selected[: int(limit)]
    return {
        "ok": True,
        "path": _rel(workspace, target),
        "total_lines": len(lines),
        "offset": start,
        "limit": None if limit is None else int(limit),
        "lines": [{"line": start + i, "text": line} for i, line in enumerate(selected)],
    }


def list_files(workspace: Path, path=".", recursive=False, glob=None):
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    if not target.exists() or not target.is_dir():
        return {"ok": False, "error": "ディレクトリが存在しません", "path": str(path)}
    iterator = target.rglob("*") if recursive else target.iterdir()
    entries = []
    for item in sorted(iterator, key=lambda p: p.as_posix()):
        if item.name in {"__pycache__", ".git"} or ".git" in item.parts:
            continue
        if glob and not fnmatch.fnmatch(item.name, str(glob)):
            continue
        entries.append(
            {
                "path": _rel(workspace, item),
                "kind": "dir" if item.is_dir() else "file",
            }
        )
    return {"ok": True, "path": _rel(workspace, target), "entries": entries}


def search_files(workspace: Path, query, path=".", glob=None):
    if not query:
        return {"ok": False, "error": "query が空です"}
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    matches = []
    files = [target] if target.is_file() else sorted(target.rglob("*"))
    for file_path in files:
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        if glob and not fnmatch.fnmatch(file_path.name, str(glob)):
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if str(query) in line:
                matches.append(
                    {
                        "path": _rel(workspace, file_path),
                        "line": index,
                        "text": line,
                    }
                )
    return {"ok": True, "query": str(query), "matches": matches}


def apply_patch(workspace: Path, path, content):
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    if target.exists() and target.is_dir():
        return {"ok": False, "error": "ディレクトリには書けません", "path": str(path)}
    before = git_diff(workspace)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("" if content is None else str(content), encoding="utf-8")
    after = git_diff(workspace)
    return {
        "ok": True,
        "path": _rel(workspace, target),
        "bytes_written": target.stat().st_size,
        "git_diff_before": before,
        "git_diff_after": after,
    }


HANDLERS = {
    "read_file": read_file,
    "list_files": list_files,
    "search_files": search_files,
    "apply_patch": apply_patch,
    "run_test": lambda workspace: run_test(workspace),
    "run_program": lambda workspace: run_program(workspace),
}


def dispatch(workspace: Path, name, arguments=None):
    arguments = arguments or {}
    handler = HANDLERS.get(name)
    if handler is None:
        return {"ok": False, "error": f"unknown_tool:{name}"}
    try:
        if name in ("run_test", "run_program"):
            return handler(workspace)
        return handler(workspace, **arguments)
    except TypeError as exc:
        return {"ok": False, "error": f"TypeError:{exc}"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}:{exc}"}


def dump_result(result):
    raw_json = json.dumps(result, ensure_ascii=False, default=str)
    truncated = len(raw_json) > TOOL_RESULT_CHAR_LIMIT
    sent = raw_json[:TOOL_RESULT_CHAR_LIMIT] + "...(truncated)" if truncated else raw_json
    try:
        raw_stored = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_stored = copy.deepcopy(result)
    return {
        "raw_result": raw_stored,
        "sent_tool_result": sent,
        "truncated": truncated,
        "sent_equals_raw_json": sent == raw_json,
        "llm_user_payload": "Tool result:\n" + sent,
    }
