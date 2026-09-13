"""Cursor 相当の最小実装処理。本番 Cursor API は使わない。

独立 fixture（runtime.py / test_runtime.py）を書き、実行し、結果を返す。
既存の liba_demo_tool は上書きしない。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORBIDDEN_VERDICTS = ("feasible", "safe", "correct")


def render_runtime(python: str, force_wrong: bool = False) -> str:
    written = "3.12" if force_wrong else (python or "UNKNOWN")
    return f'''"""LibA fixture runtime — Cursor 相当のファイル変更先。Production ではない。"""
from __future__ import annotations

from typing import Any

RUNTIME_PYTHON = {written!r}


def process(value: Any) -> dict[str, Any]:
    return {{"ok": True, "runtime": RUNTIME_PYTHON, "value": value}}
'''


def render_test_runtime(expected_python: str) -> str:
    return f'''"""LibA fixture tests — Cursor 相当のテスト実行先。"""
from runtime import RUNTIME_PYTHON, process


def test_runtime_matches_spec() -> None:
    assert RUNTIME_PYTHON == {expected_python!r}


def test_process_returns_object() -> None:
    out = process({{"x": 1}})
    assert out["ok"] is True
    assert out["runtime"] == RUNTIME_PYTHON
'''


def write_fixture_project(
    dest: Path,
    *,
    python: str,
    force_wrong: bool = False,
) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    runtime_path = dest / "runtime.py"
    test_path = dest / "test_runtime.py"
    runtime_path.write_text(render_runtime(python, force_wrong=force_wrong), encoding="utf-8")
    test_path.write_text(render_test_runtime(python), encoding="utf-8")
    return {
        "changed_files": [str(runtime_path), str(test_path)],
        "runtime_path": str(runtime_path),
        "test_path": str(test_path),
        "python_written": "3.12" if force_wrong else python,
        "python_expected": python,
        "overwrote_liba_demo": False,
        "cursor_api": False,
    }


def run_fixture_tests(dest: Path, *, expected_python: str) -> dict[str, Any]:
    import hashlib
    import sys

    runtime_path = dest / "runtime.py"
    body = runtime_path.read_bytes()
    name = "r3_rt_" + hashlib.sha256(body).hexdigest()[:16]
    sys.modules.pop(name, None)
    cache = dest / "__pycache__"
    if cache.is_dir():
        for pyc in cache.glob("runtime*.pyc"):
            pyc.unlink()
    spec = importlib.util.spec_from_file_location(name, runtime_path)
    if spec is None or spec.loader is None:
        return _result(False, 0, ["load_failed"], expected_python, "")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    observed = str(getattr(mod, "RUNTIME_PYTHON", ""))
    passed = 0
    failed: list[str] = []
    try:
        assert observed == expected_python
        passed += 1
    except Exception as exc:  # noqa: BLE001
        failed.append(f"runtime_matches_spec: {exc}")
    try:
        out = mod.process({"x": 1})
        assert out["ok"] is True
        assert out["runtime"] == observed
        passed += 1
    except Exception as exc:  # noqa: BLE001
        failed.append(f"process: {exc}")
    return _result(not failed, passed, failed, expected_python, observed)


def _result(
    ok: bool,
    passed: int,
    failed: list[str],
    expected: str,
    observed: str,
) -> dict[str, Any]:
    return {
        "test_status": "PASS" if ok else "FAIL",
        "ok": ok,
        "test_count": passed + len(failed),
        "passed": passed,
        "failed": failed,
        "expected_python": expected,
        "runtime_observed": observed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "live_network": False,
        "verdicts": {k: None for k in FORBIDDEN_VERDICTS},
    }


def apply_runtime_patch(dest: Path, python: str) -> dict[str, Any]:
    """失敗後の修正。runtime の Version 行だけ直す。全ファイルを作り直さない。"""
    runtime_path = dest / "runtime.py"
    runtime_path.write_text(render_runtime(python, force_wrong=False), encoding="utf-8")
    return {"changed_files": [str(runtime_path)], "python_written": python, "patch": "runtime_only"}
