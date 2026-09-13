"""Close Gap 1: save evidence, remeasure Current State, ask next Gap once.

Does not modify Stage 1 run 20260909T021821Z.
Does not implement the next Gap.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.completion_gap_v0.run_stage1 import (
    SYSTEM,
    TECHNICAL_SPEC,
    USER_QUESTION,
    WORKSPACE,
    _dump,
    build_user,
    classify,
)
from research.grill_observation_v0.natural_exit_v0.run import call_freeform

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
WINDOW_LOOP = WORKSPACE / "window_loop.py"
TEST_PATH = HERE / "tests" / "test_window_loop_gap.py"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def list_workspace_files() -> list[str]:
    if not WORKSPACE.is_dir():
        return []
    return sorted(
        str(p.relative_to(WORKSPACE)).replace("\\", "/")
        for p in WORKSPACE.rglob("*")
        if p.is_file()
    )


def observed_window_loop() -> dict[str, Any]:
    if not WINDOW_LOOP.is_file():
        return {"present": False}
    src = WINDOW_LOOP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assigns = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, int):
                assigns[n.targets[0].id] = n.value.value
    return {
        "present": True,
        "path": str(WINDOW_LOOP),
        "function_names": names,
        "int_constants": assigns,
    }


def run_gap_tests() -> dict[str, Any]:
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(TEST_PATH), "-q"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(ROOT),
    )
    return {
        "command": [sys.executable, "-m", "pytest", str(TEST_PATH), "-q"],
        "cwd": str(ROOT),
        "env": {"SDL_VIDEODRIVER": "dummy"},
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def measure_current_state(test_result: dict[str, Any] | None) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    py = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    pg = subprocess.run(
        [sys.executable, "-c", "import pygame; print(pygame.version.ver)"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    loop = observed_window_loop()
    implemented = []
    if loop.get("present"):
        implemented.append("window_loop.py functions: " + ", ".join(loop.get("function_names") or []))
        constants = loop.get("int_constants") or {}
        if constants:
            implemented.append("int constants: " + json.dumps(constants))
    else:
        implemented.append("NOT OBSERVED: window_loop.py missing")
    return {
        "kind": "observed_facts",
        "experiment_workspace": str(WORKSPACE),
        "files_in_workspace": list_workspace_files(),
        "implemented_content": implemented,
        "window_loop": loop,
        "python": (py.stdout or "").strip() if py.returncode == 0 else None,
        "pygame_import_ok": pg.returncode == 0,
        "pygame_version": (pg.stdout or "").strip() if pg.returncode == 0 else None,
        "pygame_import_error": (pg.stderr or "").strip() if pg.returncode != 0 else None,
        "tests": {
            "ran": test_result is not None,
            "path": str(TEST_PATH),
            "passed": bool(test_result and test_result.get("passed")),
            "returncode": None if test_result is None else test_result.get("returncode"),
            "stdout": None if test_result is None else test_result.get("stdout"),
        },
        "errors": [] if (test_result and test_result.get("passed")) else (
            [{"test_failed": test_result}] if test_result else []
        ),
        "last_completed_gap": "ゲームウィンドウの初期化と基本的なゲームループ",
        "note": "Facts only. Tetromino/grid/collision are not claimed.",
    }


def main() -> int:
    test_result = run_gap_tests()
    state = measure_current_state(test_result)
    user = build_user(TECHNICAL_SPEC, state)
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = _utc()
    run_dir = RUNS / run_id
    cycle_dir = run_dir / "cycle_after_gap1"
    cycle_dir.mkdir(parents=True, exist_ok=True)

    evidence = {
        "gap": "ゲームウィンドウの初期化と基本的なゲームループ",
        "changed_files": [
            str(WINDOW_LOOP),
            str(HERE / "workspace" / "__init__.py"),
            str(HERE / "tests" / "conftest.py"),
            str(TEST_PATH),
        ],
        "implementation": "init_window 300x600, handle_events QUIT, empty update, draw+flip, run_one_iteration, shutdown, run_forever not used by tests",
        "tests": test_result,
        "parent_stage1_run": "20260909T021821Z",
        "note": "New evidence run. Stage 1 run files were not rewritten.",
    }
    _dump(cycle_dir / "evidence.json", evidence)
    _dump(cycle_dir / "test_result.json", test_result)
    (cycle_dir / "technical_specification.txt").write_text(TECHNICAL_SPEC, encoding="utf-8")
    _dump(cycle_dir / "current_state.json", state)

    call = call_freeform(
        model=provider,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label="gap_after_gap1",
    )
    raw = str(call.get("raw_text") or "")
    judged = classify(raw)
    (cycle_dir / "gap_grill_system.txt").write_text(SYSTEM, encoding="utf-8")
    (cycle_dir / "gap_grill_user.txt").write_text(user, encoding="utf-8")
    (cycle_dir / "qwen_raw.txt").write_text(raw, encoding="utf-8")
    _dump(cycle_dir / "classification.json", judged)
    record = {
        "experiment": "completion_gap_v0",
        "stage": "1.5_close_one_gap",
        "run_id": run_id,
        "model": provider,
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "classification": judged["classification"],
        "selected_gap": judged["selected_gap"],
        "completed_gap": "ゲームウィンドウの初期化と基本的なゲームループ",
        "stopped": "after_next_gap_grill_no_impl",
        "parent_stage1_run": "20260909T021821Z",
    }
    _dump(run_dir / "run.json", record)
    print(raw, flush=True)
    print(f"CLASSIFICATION {judged['classification']}", flush=True)
    print(f"SELECTED_GAP {judged['selected_gap']}", flush=True)
    print(f"RUN {run_dir}", flush=True)
    print("STOPPED. Next gap not implemented.", flush=True)
    return 0 if test_result.get("passed") and not call.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
