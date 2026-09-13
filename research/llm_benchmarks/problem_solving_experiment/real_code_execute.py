"""実コード実験の実行記録。人工エラー文字列は作らない。"""

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
    traceback = stderr if "Traceback (most recent call last):" in stderr else ""
    return {
        "command": list(command),
        "working_directory": str(Path(cwd).resolve()),
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": completed.returncode,
        "traceback": traceback,
        "execution_time": elapsed,
    }


def run_main(cwd):
    return run_command([sys.executable, "main.py"], cwd=cwd)


def run_pytest(cwd):
    return run_command(
        [sys.executable, "-m", "pytest", "tests/test_main.py", "-q"],
        cwd=cwd,
    )


def initial_execution(cwd):
    main_run = run_main(cwd)
    test_run = run_pytest(cwd)
    return {
        "main_py": main_run,
        "pytest": test_run,
        "captured_at": None,
    }


def pytest_flags(result):
    stderr = result.get("stderr") or ""
    stdout = result.get("stdout") or ""
    combined = stdout + "\n" + stderr
    exit_code = result.get("exit_code")
    assertion_failed = "AssertionError" in combined
    runtime_error = any(
        name in combined
        for name in ("IndexError", "KeyError", "TypeError", "AttributeError", "NameError")
    )
    return {
        "execution_success": exit_code == 0 or (assertion_failed and not runtime_error),
        "test_assertion_success": exit_code == 0,
        "expected_behavior": 'build_report()["status"] == "Busy"',
        "actual_behavior": combined.strip()[-800:] or "NOT_OBSERVED",
        "solution_correct": "NOT_AUTO_SCORED",
    }


def format_execution_block(title, payload):
    return (
        f"{title}\n"
        f"command: {json.dumps(payload['command'], ensure_ascii=False)}\n"
        f"exit_code: {payload['exit_code']}\n"
        f"stdout:\n{payload['stdout']}"
        f"stderr:\n{payload['stderr']}"
    )
