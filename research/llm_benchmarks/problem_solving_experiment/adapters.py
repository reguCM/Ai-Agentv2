"""実験用ディスパッチが呼ぶ既存関数の束ね。本番 Registry / Repair には登録しない。"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from tools.file.workspace.list_files import list_files
from tools.file.workspace.read_file import read_file
from tools.file.workspace.search_files import search_files
from tools.file.workspace._paths import path_error, resolve_under_workspace, to_workspace_relative


SESSION: dict[str, Any] = {
    "test_result": None,
    "validation": None,
    "source": None,
    "tool_name": None,
}


def set_session(*, test_result=None, validation=None, source=None, tool_name=None):
    SESSION["test_result"] = test_result
    SESSION["validation"] = validation
    SESSION["source"] = source
    SESSION["tool_name"] = tool_name


def get_current_failure():
    """実験セッションが保持している Failure 面。Schema 拡張ではない。"""
    test_result = SESSION.get("test_result") or {}
    validation = SESSION.get("validation") or {}
    return {
        "ok": True,
        "tool_name": SESSION.get("tool_name"),
        "test_result": test_result,
        "validation": {
            "status": validation.get("status"),
            "errors": validation.get("errors") or [],
            "warnings": validation.get("warnings") or [],
            "warning_items": validation.get("warning_items") or [],
            "missing_outputs": validation.get("missing_outputs") or [],
        },
        "source": SESSION.get("source"),
    }


def get_execution_environment():
    """実装前ベンチの verified_environment と、executable / venv / cwd。本番経路へは接続しない。"""
    from research.llm_benchmarks.environment_benchmark import verified_environment

    payload = dict(verified_environment())
    payload["ok"] = True
    payload["python_executable"] = sys.executable
    payload["virtual_env"] = os.environ.get("VIRTUAL_ENV")
    payload["cwd"] = os.getcwd()
    return payload


def read_git_diff():
    from ai_tool.chat_interface.dev_readonly import git_snapshot

    return git_snapshot()


def request_human_help(reason, questions=None):
    if isinstance(questions, str):
        questions = [questions]
    return {
        "ok": True,
        "help_requested": True,
        "reason": reason,
        "questions": list(questions or []),
    }


def read_pdf(path, page=None, max_chars=4000):
    target = resolve_under_workspace(path, allow_directory=False)
    if isinstance(target, dict):
        return target
    if not target.exists() or not target.is_file():
        return path_error("PDF ファイルがありません", path=path)
    try:
        from pypdf import PdfReader
    except ImportError:
        return {
            "ok": False,
            "path": to_workspace_relative(target),
            "error": "pdf_library_not_installed",
            "hint": "この Repository の依存には PDF ライブラリが無い。実験では未充足として記録する。",
        }
    try:
        reader = PdfReader(str(target))
        pages = list(reader.pages)
        if page is None:
            texts = [(i + 1, pages[i].extract_text() or "") for i in range(len(pages))]
        else:
            index = int(page) - 1
            if index < 0 or index >= len(pages):
                return path_error(f"page が範囲外です: {page}", path=path)
            texts = [(int(page), pages[index].extract_text() or "")]
        chunks = []
        remaining = int(max_chars)
        for number, text in texts:
            if remaining <= 0:
                break
            piece = text[:remaining]
            chunks.append({"page": number, "text": piece})
            remaining -= len(piece)
        return {
            "ok": True,
            "path": to_workspace_relative(target),
            "page_count": len(pages),
            "pages": chunks,
            "truncated": remaining <= 0,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": to_workspace_relative(target),
            "error": f"{type(exc).__name__}:{exc}",
        }


def experiment_test_source(source, function_name="cpu_status"):
    """
    与えられたソースを一時ファイルで実行する。本番 cpu_status.py と apply_repair は使わない。
    """
    if not source or not str(source).strip():
        return {"ok": False, "error": "source が空です"}
    if "def " + str(function_name) not in source:
        return {
            "ok": False,
            "error": f"source に def {function_name} がありません",
        }
    runner = r"""
import importlib.util
import json
import sys
import traceback

path = sys.argv[1]
name = sys.argv[2]
spec = importlib.util.spec_from_file_location("experiment_candidate", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = getattr(mod, name, None)
if fn is None:
    print(json.dumps({"ok": False, "status": "fail", "error": "function_missing", "error_type": "AttributeError"}))
    raise SystemExit(0)
try:
    value = fn()
    print(json.dumps({"ok": True, "status": "pass", "return_value": value, "error": None, "error_type": None}, default=str))
except Exception as exc:
    print(json.dumps({
        "ok": False,
        "status": "fail",
        "return_value": None,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "traceback": traceback.format_exc(),
    }))
"""
    with tempfile.TemporaryDirectory() as tmp:
        src_path = Path(tmp) / "candidate.py"
        run_path = Path(tmp) / "runner.py"
        src_path.write_text(str(source).strip() + "\n", encoding="utf-8")
        run_path.write_text(runner, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, str(run_path), str(src_path), str(function_name)],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "status": "fail", "error": "timeout", "error_type": "TimeoutError"}
    if not completed.stdout.strip():
        return {
            "ok": False,
            "status": "fail",
            "error": completed.stderr.strip() or "no_stdout",
            "error_type": "RuntimeError",
        }
    try:
        return json.loads(completed.stdout.splitlines()[-1])
    except json.JSONDecodeError:
        return {
            "ok": False,
            "status": "fail",
            "error": completed.stdout[:500],
            "stderr": completed.stderr[:500],
            "error_type": "JSONDecodeError",
        }


def get_gpu_status():
    from tools.system.gpu.gpu_status import get_gpu_status as _fn

    return _fn()


def get_gpu_processes():
    from tools.system.gpu.gpu_processes import get_gpu_processes as _fn

    return _fn()


def search_web(query, limit=None):
    from tools.system.network.search_web import search_web as _fn

    if limit is None:
        return _fn(query)
    return _fn(query, limit=limit)


def read_url_text(url, max_bytes=None, timeout_seconds=None):
    from ai_tool.experimental.read_url.reader import read_url_text as _fn

    kwargs = {"url": url}
    if max_bytes is not None:
        kwargs["max_bytes"] = max_bytes
    if timeout_seconds is not None:
        kwargs["timeout_seconds"] = timeout_seconds
    return _fn(**kwargs)


EXISTING_FILE_TOOLS = {
    "read_file": read_file,
    "search_files": search_files,
    "list_files": list_files,
}
