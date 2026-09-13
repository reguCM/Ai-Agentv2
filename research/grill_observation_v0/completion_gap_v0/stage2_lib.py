"""Stage 2 helpers: measure workspace, Gap Grill, save cycle artifacts."""
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
TESTS = HERE / "tests"


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def workspace_py_facts() -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if not WORKSPACE.is_dir():
        return facts
    for path in sorted(WORKSPACE.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        assigns: dict[str, Any] = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                if isinstance(n.value, ast.Constant) and isinstance(n.value.value, (int, str)):
                    assigns[n.targets[0].id] = n.value.value
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                if isinstance(n.value, ast.Constant) and isinstance(n.value.value, (int, str)):
                    assigns[n.target.id] = n.value.value
        facts.append(
            {
                "file": path.name,
                "functions": names,
                "simple_constants": assigns,
            }
        )
    return facts


def list_workspace_files() -> list[str]:
    if not WORKSPACE.is_dir():
        return []
    return sorted(
        str(p.relative_to(WORKSPACE)).replace("\\", "/")
        for p in WORKSPACE.rglob("*")
        if p.is_file() and "__pycache__" not in str(p)
    )


def run_pytest(rel_or_abs: str) -> dict[str, Any]:
    path = Path(rel_or_abs)
    if not path.is_absolute():
        path = TESTS / rel_or_abs
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(path), "-q"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(ROOT),
    )
    return {
        "command": ["python", "-m", "pytest", str(path), "-q"],
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def measure(test_result: dict[str, Any] | None, completed_gaps: list[str]) -> dict[str, Any]:
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
    errors: list[Any] = []
    if test_result is not None and not test_result.get("passed"):
        errors.append({"test_failed": True, "returncode": test_result.get("returncode")})
    return {
        "kind": "observed_facts",
        "experiment_workspace": str(WORKSPACE),
        "files_in_workspace": list_workspace_files(),
        "python_modules": workspace_py_facts(),
        "python": (py.stdout or "").strip() if py.returncode == 0 else None,
        "pygame_import_ok": pg.returncode == 0,
        "pygame_version": (pg.stdout or "").strip() if pg.returncode == 0 else None,
        "tests": {
            "ran": test_result is not None,
            "passed": None if test_result is None else bool(test_result.get("passed")),
            "stdout": None if test_result is None else test_result.get("stdout"),
        },
        "errors": errors,
        "completed_gaps": list(completed_gaps),
        "last_completed_gap": completed_gaps[-1] if completed_gaps else None,
        "note": "Facts from workspace files and test process. No inferred features.",
    }


def grill(state: dict[str, Any]) -> dict[str, Any]:
    user = build_user(TECHNICAL_SPEC, state)
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
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
        label="stage2_gap",
    )
    raw = str(call.get("raw_text") or "")
    judged = classify(raw)
    return {
        "model": provider,
        "user": user,
        "system": SYSTEM,
        "raw": raw,
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "classification": judged["classification"],
        "selected_gap": judged["selected_gap"],
        "judged": judged,
    }


def save_cycle(run_dir: Path, cycle_no: int, payload: dict[str, Any]) -> Path:
    cycle_dir = run_dir / f"cycle_{cycle_no}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    (cycle_dir / "technical_specification.txt").write_text(TECHNICAL_SPEC, encoding="utf-8")
    _dump(cycle_dir / "current_state.json", payload.get("current_state") or {})
    _dump(cycle_dir / "focus.json", payload.get("focus") or {})
    _dump(cycle_dir / "evidence.json", payload.get("evidence") or {})
    if payload.get("test_result") is not None:
        _dump(cycle_dir / "test_result.json", payload["test_result"])
    grill_out = payload.get("grill")
    if grill_out:
        (cycle_dir / "gap_grill_system.txt").write_text(str(grill_out.get("system") or ""), encoding="utf-8")
        (cycle_dir / "gap_grill_user.txt").write_text(str(grill_out.get("user") or ""), encoding="utf-8")
        (cycle_dir / "qwen_raw.txt").write_text(str(grill_out.get("raw") or ""), encoding="utf-8")
        _dump(cycle_dir / "classification.json", grill_out.get("judged") or {})
    _dump(cycle_dir / "cycle.json", {k: v for k, v in payload.items() if k != "grill"})
    return cycle_dir
