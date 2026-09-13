"""実験専用 Tool。本番 Registry / 既存実験 workspace には接続しない。"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


FIXTURE_SRC = Path(__file__).resolve().parent / "fixtures" / "slot_ready"
TOOL_RESULT_CHAR_LIMIT = 4000
_ASSIGN = re.compile(r"^(\s*)([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")


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


def workspace_filenames(workspace: Path):
    names = []
    for item in sorted(workspace.rglob("*")):
        if not item.is_file() or ".git" in item.parts or item.suffix == ".pyc":
            continue
        if ".pytest_cache" in item.parts:
            continue
        names.append(item.resolve().relative_to(workspace.resolve()).as_posix())
    return names


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
    text = target.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    start = 1 if offset is None else int(offset)
    if start < 1:
        return {"ok": False, "error": "offset は 1 以上である必要があります"}
    selected = lines[start - 1 :]
    if limit is not None:
        selected = selected[: int(limit)]
    return {
        "ok": True,
        "path": _rel(workspace, target),
        "text": "\n".join(selected),
        "total_lines": len(lines),
    }


def list_files(workspace: Path, path=".", recursive=True, glob=None):
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
        entries.append({"path": _rel(workspace, item), "kind": "dir" if item.is_dir() else "file"})
    return {"ok": True, "path": _rel(workspace, target), "entries": entries}


def search_files(workspace: Path, query, path=".", glob=None):
    if not query:
        return {"ok": False, "error": "query が空です"}
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    matches = []
    definitions = []
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
        rel = _rel(workspace, file_path)
        for index, line in enumerate(text.splitlines(), start=1):
            if str(query) not in line:
                continue
            hit = {"path": rel, "line": index, "text": line}
            matches.append(hit)
            assigned = _ASSIGN.match(line)
            if assigned and assigned.group(2) == str(query):
                definitions.append(hit)
    unique_files = sorted({item["path"] for item in matches})
    unique_definition_files = sorted({item["path"] for item in definitions})
    unique_path = None
    unique_reason = "not_unique"
    if len(unique_definition_files) == 1:
        unique_path = unique_definition_files[0]
        unique_reason = "unique_assignment"
    elif len(unique_files) == 1:
        unique_path = unique_files[0]
        unique_reason = "unique_mention"
    return {
        "ok": True,
        "query": str(query),
        "matches": matches,
        "definitions": definitions,
        "unique_files": unique_files,
        "unique_definition_files": unique_definition_files,
        "unique_path": unique_path,
        "unique_reason": unique_reason,
    }


def apply_patch(workspace: Path, path, content=None, assignments=None):
    target = resolve_in_workspace(workspace, path)
    if isinstance(target, dict):
        return target
    if target.exists() and target.is_dir():
        return {"ok": False, "error": "ディレクトリには書けません", "path": str(path)}
    before = git_diff(workspace)
    if assignments:
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": "ファイルが存在しません", "path": str(path)}
        text = target.read_text(encoding="utf-8", errors="replace")
        updated, error = apply_assignments(text, assignments)
        if error:
            return {"ok": False, "error": error, "path": str(path)}
        content = updated
    elif content is None:
        return {"ok": False, "error": "content も assignments もありません", "path": str(path)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(content), encoding="utf-8")
    after = git_diff(workspace)
    return {
        "ok": True,
        "path": _rel(workspace, target),
        "bytes_written": target.stat().st_size,
        "git_diff_before": before,
        "git_diff_after": after,
    }


def apply_assignments(text, assignments):
    current = text
    for item in assignments:
        name = item.get("name")
        value = item.get("value")
        if not name:
            return current, "assignment name が空です"
        pattern = re.compile(rf"^(\s*{re.escape(name)}\s*=\s*).*$", re.M)
        if not pattern.search(current):
            return current, f"assignment_not_found:{name}"
        current = pattern.sub(rf"\g<1>{value}", current, count=1)
    return current, None


def run_command(command, *, cwd, timeout=30):
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": list(command),
            "working_directory": str(Path(cwd).resolve()),
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "exit_code": None,
            "traceback": "",
            "error": "TimeoutExpired",
            "execution_time": time.perf_counter() - started,
        }
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = stdout + "\n" + stderr
    traceback = combined if "Traceback (most recent call last):" in combined else ""
    return {
        "ok": completed.returncode == 0,
        "command": list(command),
        "working_directory": str(Path(cwd).resolve()),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": completed.returncode,
        "traceback": traceback,
        "execution_time": time.perf_counter() - started,
    }


def run_program(cwd):
    return run_command([sys.executable, "main.py"], cwd=cwd)


def run_test(cwd):
    return run_command(
        [sys.executable, "-m", "pytest", "tests/test_main.py", "-q"],
        cwd=cwd,
    )


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
    return {
        "raw_result": json.loads(raw_json) if raw_json else result,
        "sent_tool_result": sent,
        "truncated": truncated,
    }
