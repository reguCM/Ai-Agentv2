"""Test後再判断実験の実実行。人工エラーは作らない。既存 execute モジュールは変更しない。"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def run_command(command, *, cwd, timeout=30):
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = time.perf_counter() - started
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = stdout + "\n" + stderr
    traceback = ""
    if "Traceback (most recent call last):" in combined:
        traceback = combined
    return {
        "command": list(command),
        "working_directory": str(Path(cwd).resolve()),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": completed.returncode,
        "traceback": traceback,
        "execution_time": elapsed,
    }


def run_program(cwd):
    return run_command([sys.executable, "main.py"], cwd=cwd)


def run_test(cwd):
    return run_command(
        [sys.executable, "-m", "pytest", "tests/test_main.py", "-q"],
        cwd=cwd,
    )


def split_outcomes(pytest_result, program_result):
    pytest_text = (pytest_result.get("stdout") or "") + "\n" + (pytest_result.get("stderr") or "")
    program_text = (program_result.get("stdout") or "") + "\n" + (program_result.get("stderr") or "")
    crashed = any(
        name in (pytest_text + program_text)
        for name in ("IndexError", "KeyError", "TypeError", "AttributeError", "NameError")
    )
    return {
        "execution_success": (not crashed) and program_result.get("exit_code") == 0,
        "test_pass": pytest_result.get("exit_code") == 0,
        "application_behavior": (program_result.get("stdout") or "").strip() or "NOT_OBSERVED",
    }


def format_execution_block(title, payload):
    return (
        f"{title}\n"
        f"command: {json.dumps(payload['command'], ensure_ascii=False)}\n"
        f"exit_code: {payload['exit_code']}\n"
        f"stdout:\n{payload['stdout']}"
        f"stderr:\n{payload['stderr']}"
    )
