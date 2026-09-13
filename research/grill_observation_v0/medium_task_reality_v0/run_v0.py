"""Medium Task Reality Loop v0 — one pass. Cursor is Observer/Harness."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.completion_gap_v0.run_stage1 import TECHNICAL_SPEC
from research.grill_observation_v0.natural_exit_v0.run import call_freeform
from research.grill_observation_v0.parse import extract_json_object

from research.grill_observation_v0.medium_task_reality_v0.actual_map import (
    measure_actual_map,
    python_env_facts,
)
from research.grill_observation_v0.medium_task_reality_v0.apply_patch import (
    apply_implementer_output,
    strip_think,
)
from research.grill_observation_v0.medium_task_reality_v0 import prompts
from research.grill_observation_v0.medium_task_reality_v0.seed import seed_workspace

WORKSPACE = HERE / "workspace"
TESTS = HERE / "tests"
RUNS = HERE / "runs"
WORKSPACE_PKG = "research.grill_observation_v0.medium_task_reality_v0.workspace"
PARENT_COMPLETE = (
    ROOT
    / "research"
    / "grill_observation_v0"
    / "completion_gap_v0"
    / "runs"
    / "20260909T023138Z"
)
FILE_TO_TEST = {
    "window_loop.py": "test_window_loop_gap.py",
    "tetromino.py": "test_tetromino_gap.py",
    "collision.py": "test_collision_gap.py",
    "line_clear.py": "test_line_clear_gap.py",
    "movement.py": "test_movement_gap.py",
    "game_over.py": "test_game_over_gap.py",
}


def utc_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def llm_call(
    *,
    system: str,
    user: str,
    label: str,
    num_predict: int | None = None,
) -> dict[str, Any]:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    predict = int(num_predict if num_predict is not None else (profile.get("num_predict") or 2048))
    call = call_freeform(
        model=provider,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=predict,
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label=label,
    )
    raw = strip_think(str(call.get("raw_text") or ""))
    parsed, parse_err = extract_json_object(raw)
    return {
        "model": provider,
        "label": label,
        "raw": raw,
        "parsed": parsed,
        "parse_error": parse_err,
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "num_predict": predict,
    }


def parent_complete_fact() -> dict[str, Any]:
    cls = PARENT_COMPLETE / "cycle_5" / "classification.json"
    cov = PARENT_COMPLETE / "coverage_at_stop.json"
    return {
        "treatment": "valid_in_local_gap_world_not_an_error",
        "run": "20260909T023138Z",
        "classification_source": str(cls),
        "classification": json.loads(cls.read_text(encoding="utf-8")) if cls.is_file() else None,
        "coverage_source": str(cov),
        "coverage": json.loads(cov.read_text(encoding="utf-8")) if cov.is_file() else None,
        "note": "Read-only evidence. Existing run was not modified.",
    }


def run_pytest(names: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    paths = [str(TESTS / n) for n in names]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-q"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=str(ROOT),
    )
    return {
        "command": ["python", "-m", "pytest", *names, "-q"],
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
        "files": names,
    }


def observer_fallback_medium_task(reviewed: dict[str, Any] | None, actual: dict[str, Any]) -> dict[str, Any]:
    unconnected = actual.get("unconnected_paths") or []
    candidates = []
    if isinstance(reviewed, dict):
        candidates = reviewed.get("medium_task_candidates") or []
    chosen = candidates[0] if candidates else {
        "name": "one_play_step_through_game_loop",
        "purpose": "ゲームループの1回の更新で、テトロミノが衝突判定を伴って落下または移動できること",
        "components": ["window_loop", "tetromino", "movement", "collision"],
    }
    gap_name = "ゲームループから落下・移動・衝突Componentが呼ばれていない"
    if isinstance(reviewed, dict) and reviewed.get("missing_connections"):
        gap_name = str(reviewed["missing_connections"][0])
    return {
        "medium_task": chosen,
        "expected_for_task": [
            "window_loop update path uses movement and collision",
            "a current piece exists as loop state",
        ],
        "actual_for_task": [u.get("fact") for u in unconnected],
        "delta": [u.get("fact") for u in unconnected],
        "gap": {
            "name": gap_name,
            "why": "Actual Map shows gameplay modules are not called from the game loop",
        },
        "source": "observer_fallback_from_maps",
    }


def map_focus(medium: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    actual_ids = [c["id"] for c in actual.get("components") or []]
    task = medium.get("medium_task") if isinstance(medium.get("medium_task"), dict) else {}
    gap = medium.get("gap") if isinstance(medium.get("gap"), dict) else {}
    names = list(task.get("components") or [])
    blob = " ".join(
        [str(task.get("name") or ""), str(task.get("purpose") or ""), str(gap.get("name") or ""), str(gap.get("why") or "")]
        + [str(n) for n in names]
    )
    mapped: list[str] = []
    aliases = {
        "window_loop": ["window", "loop", "ループ", "ゲームループ"],
        "tetromino": ["tetromino", "テトロミノ", "spawn", "形状"],
        "collision": ["collision", "衝突"],
        "movement": ["movement", "move", "落下", "移動", "回転"],
        "line_clear": ["line_clear", "ライン", "行の削除"],
        "game_over": ["game_over", "ゲームオーバー"],
    }
    for stem, keys in aliases.items():
        if stem not in actual_ids:
            continue
        if any(k.lower() in blob.lower() or k in blob for k in keys):
            mapped.append(stem)
        for n in names:
            if stem in str(n).lower() or str(n).lower() in stem:
                mapped.append(stem)
    mapped = list(dict.fromkeys(mapped))
    if not mapped:
        mapped = [i for i in ("window_loop", "movement", "collision", "tetromino") if i in actual_ids]
    integration = (
        len(mapped) >= 2
        or any(k in blob for k in ("接続", "統合", "呼", "組み合わせ", "ループ"))
    )
    allowed_read = [f"workspace/{s}.py" for s in mapped]
    allowed_write = ["workspace/window_loop.py", "tests/test_medium_task_v0.py"] if integration else [
        f"workspace/{mapped[0]}.py"
    ]
    if not integration and mapped:
        allowed_write = [f"workspace/{mapped[0]}.py", "tests/test_medium_task_v0.py"]
    horizontal = integration
    return {
        "gap": gap,
        "minimum_focus": mapped,
        "assets": [
            "completion_gap TECHNICAL_SPEC",
            "Reviewed Expected Map",
            "Actual Map",
            str(PARENT_COMPLETE / "coverage_at_stop.json"),
        ],
        "vertical_map": False,
        "vertical_map_reason": "spec meaning of loop update vs components is already explicit",
        "horizontal_map": horizontal,
        "horizontal_map_reason": (
            "Gap spans multiple components and implied shared piece/grid state"
            if horizontal
            else None
        ),
        "horizontal_design_check": {
            "used": horizontal,
            "shared_state_question": "who holds current piece, grid, score, last_fall_ms",
            "actual_joint_owner": "NOT OBSERVED in any single module before this Gap",
            "provisional": "state may live in window_loop for this Gap; new module is out of Focus",
        }
        if horizontal
        else {"used": False},
        "focus_expanded": False,
        "expand_reason": None,
        "minimum_sufficient_focus": {
            "write": allowed_write,
            "read": allowed_read,
            "do_not": [
                "lock-piece as a separate Gap unless already in this Gap text",
                "grid/piece drawing",
                "score UI / level",
                "Production Runtime",
            ],
        },
        "allowed_write": allowed_write,
        "allowed_read": allowed_read,
        "note": "alias mapping is provisional observer heuristic from Actual Map ids",
    }


def file_context(paths: list[str]) -> str:
    chunks: list[str] = []
    for rel in paths:
        path = HERE / rel
        if not path.is_file():
            chunks.append(f"# MISSING {rel}\n")
            continue
        chunks.append(f"# FILE {rel}\n{path.read_text(encoding='utf-8')}\n")
    return "\n".join(chunks)


def tests_for_changes(changed: list[str]) -> list[str]:
    names: list[str] = []
    for rel in changed:
        base = Path(rel).name
        if base.startswith("test_") and base.endswith(".py"):
            names.append(base)
        mapped = FILE_TO_TEST.get(base)
        if mapped:
            names.append(mapped)
    if not names:
        names = ["test_window_loop_gap.py"]
    return list(dict.fromkeys(names))


def loop_connected_to(actual: dict[str, Any], stems: list[str]) -> dict[str, bool]:
    found = {s: False for s in stems}
    for e in actual.get("import_edges") or []:
        if e.get("from") != "window_loop":
            continue
        for s in stems:
            if s in str(e.get("to_module") or "") or s in str(e.get("names") or ""):
                found[s] = True
    for e in actual.get("call_edges") or []:
        if e.get("from_file") != "window_loop":
            continue
        for s in stems:
            if e.get("to_file") == s:
                found[s] = True
    return found


def classify_recheck(
    *,
    apply_result: dict[str, Any],
    test_result: dict[str, Any] | None,
    actual_after: dict[str, Any],
    focus: dict[str, Any],
    skipped_implementer: bool,
) -> dict[str, Any]:
    targets = [s for s in focus.get("minimum_focus") or [] if s != "window_loop"]
    connected = loop_connected_to(actual_after, targets)
    apply_ok = bool(apply_result.get("applied")) and not apply_result.get("errors")
    test_ok = bool(test_result and test_result.get("passed"))
    all_connected = bool(targets) and all(connected.values())
    if skipped_implementer:
        status = "CLOSED" if all_connected else "NEW_GAP"
        reason = "no implementer because maps had no delta" if skipped_implementer else ""
    elif apply_result.get("errors") or apply_result.get("rejected") and not apply_result.get("applied"):
        status = "BLOCKED"
        reason = "implementer patch did not apply; Cursor did not repair the code"
    elif not test_ok:
        status = "BLOCKED"
        reason = "minimal tests failed; Cursor did not repair the code"
    elif all_connected and test_ok and apply_ok:
        status = "CLOSED"
        reason = "window_loop now connects to Medium Task components and tests passed"
    else:
        status = "NEW_GAP"
        missing = [k for k, v in connected.items() if not v]
        reason = "tests may have passed but Medium Task connections still missing: " + ",".join(missing)
    next_gap = None
    if status == "NEW_GAP":
        missing = [k for k, v in connected.items() if not v]
        next_gap = {
            "name": "ゲームループがまだ Medium Task の Component を呼んでいない",
            "missing_connections": missing,
            "note": "Second repair is out of scope for this run",
        }
    return {
        "status": status,
        "reason": reason,
        "connected": connected,
        "next_gap": next_gap,
        "complete_is_not_product_complete": True,
    }


def main() -> int:
    run_id = utc_id()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    parent = parent_complete_fact()
    dump(run_dir / "parent_local_complete.json", parent)
    write_text(run_dir / "technical_specification.txt", TECHNICAL_SPEC)

    seed_info = seed_workspace()
    dump(run_dir / "seed.json", seed_info)
    shutil.copytree(WORKSPACE, run_dir / "workspace_before", ignore=shutil.ignore_patterns("__pycache__"))

    # Phase 1 Planner
    planner_user = prompts.PLANNER_USER.format(spec=TECHNICAL_SPEC)
    planner = llm_call(system=prompts.PLANNER_SYSTEM, user=planner_user, label="phase1_planner")
    write_text(run_dir / "phase1_planner_raw.txt", planner["raw"])
    dump(run_dir / "phase1_planner.json", {k: v for k, v in planner.items() if k != "raw"})
    expected_map = planner["parsed"] if isinstance(planner["parsed"], dict) else {"raw_unparsed": True, "text": planner["raw"]}
    dump(run_dir / "expected_map_v0.json", expected_map)

    # Phase 1 Reviewer
    reviewer_user = prompts.REVIEWER_USER.format(
        spec=TECHNICAL_SPEC,
        expected_map=json.dumps(expected_map, ensure_ascii=False, indent=2),
    )
    reviewer = llm_call(system=prompts.REVIEWER_SYSTEM, user=reviewer_user, label="phase1_reviewer")
    write_text(run_dir / "phase1_reviewer_raw.txt", reviewer["raw"])
    dump(run_dir / "phase1_reviewer.json", {k: v for k, v in reviewer.items() if k != "raw"})
    reviewed = reviewer["parsed"] if isinstance(reviewer["parsed"], dict) else {
        "raw_unparsed": True,
        "expected_map": expected_map,
        "text": reviewer["raw"],
    }
    if isinstance(reviewed, dict) and "expected_map_v0" not in reviewed:
        reviewed = dict(reviewed)
        reviewed["expected_map_v0"] = expected_map
    dump(run_dir / "reviewed_expected_map.json", reviewed)

    # Phase 2 Actual
    env_facts = python_env_facts()
    actual_before = measure_actual_map(workspace=WORKSPACE, tests=TESTS, workspace_pkg=WORKSPACE_PKG)
    actual_before["env"] = env_facts
    dump(run_dir / "actual_map_before.json", actual_before)

    # Phase 3 Medium Task
    medium_user = prompts.MEDIUM_TASK_USER.format(
        reviewed=json.dumps(reviewed, ensure_ascii=False, indent=2),
        actual=json.dumps(actual_before, ensure_ascii=False, indent=2),
    )
    medium_llm = llm_call(system=prompts.MEDIUM_TASK_SYSTEM, user=medium_user, label="phase3_medium_task")
    write_text(run_dir / "phase3_medium_task_raw.txt", medium_llm["raw"])
    dump(run_dir / "phase3_medium_task.json", {k: v for k, v in medium_llm.items() if k != "raw"})
    if isinstance(medium_llm["parsed"], dict) and (medium_llm["parsed"].get("medium_task") or medium_llm["parsed"].get("gap")):
        medium = dict(medium_llm["parsed"])
        medium["source"] = "local_medium_task"
    else:
        medium = observer_fallback_medium_task(reviewed if isinstance(reviewed, dict) else None, actual_before)
        medium["llm_parse_error"] = medium_llm.get("parse_error")
    dump(run_dir / "medium_task.json", medium)

    gap = medium.get("gap") if isinstance(medium.get("gap"), dict) else {}
    gap_name = str(gap.get("name") or "").strip()
    delta = medium.get("delta") or []
    no_delta = (not delta) and (not gap_name)

    # Phase 4 Focus
    focus = map_focus(medium, actual_before)
    dump(run_dir / "focus.json", focus)

    apply_result: dict[str, Any] = {"applied": [], "rejected": [], "errors": ["skipped_no_delta"], "would_write": []}
    implementer: dict[str, Any] | None = None
    test_result: dict[str, Any] | None = None
    skipped = False

    if no_delta:
        skipped = True
        shutil.copytree(WORKSPACE, run_dir / "workspace_after", ignore=shutil.ignore_patterns("__pycache__"))
    else:
        # Phase 5 Local-Implementer
        # Provisional: code patches often exceed grill num_predict=2048 (grill_to_code_v0 truncation).
        impl_user = prompts.IMPLEMENTER_USER.format(
            spec=TECHNICAL_SPEC,
            medium_task=json.dumps(medium.get("medium_task"), ensure_ascii=False, indent=2),
            gap=json.dumps(gap, ensure_ascii=False, indent=2),
            focus=json.dumps(focus.get("minimum_sufficient_focus"), ensure_ascii=False, indent=2),
            allowed_write="\n".join(focus["allowed_write"]),
            file_context=file_context(list(dict.fromkeys(focus["allowed_read"] + focus["allowed_write"]))),
            actual_excerpt=json.dumps(
                {
                    "unconnected_paths": actual_before.get("unconnected_paths"),
                    "import_edges": actual_before.get("import_edges"),
                    "call_edges": actual_before.get("call_edges"),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        implementer = llm_call(
            system=prompts.IMPLEMENTER_SYSTEM,
            user=impl_user,
            label="phase5_implementer",
            num_predict=4096,
        )
        write_text(run_dir / "phase5_implementer_raw.txt", implementer["raw"])
        dump(
            run_dir / "phase5_implementer.json",
            {
                "elapsed_s": implementer.get("elapsed_s"),
                "error": implementer.get("error"),
                "num_predict": implementer.get("num_predict"),
                "parse_error": implementer.get("parse_error"),
                "note": "num_predict=4096 is a provisional harness override; model id is still pipeline qwen3_14b",
            },
        )
        apply_result = apply_implementer_output(
            implementer["raw"],
            here=HERE,
            allowed_write=set(focus["allowed_write"]),
        )
        dump(run_dir / "phase5_apply.json", apply_result)
        write_text(run_dir / "phase5_implementer_user.txt", impl_user)
        shutil.copytree(WORKSPACE, run_dir / "workspace_after", ignore=shutil.ignore_patterns("__pycache__"))

        # Phase 6 Verification
        changed = list(apply_result.get("would_write") or [])
        test_names = [n for n in tests_for_changes(changed) if (TESTS / n).is_file()]
        if test_names:
            test_result = run_pytest(test_names)
        else:
            test_result = {
                "passed": False,
                "files": tests_for_changes(changed),
                "stdout": "",
                "stderr": "no_matching_test_files",
                "returncode": None,
            }
        dump(run_dir / "phase6_test.json", test_result)

    actual_after = measure_actual_map(workspace=WORKSPACE, tests=TESTS, workspace_pkg=WORKSPACE_PKG)
    actual_after["env"] = env_facts
    dump(run_dir / "actual_map_after.json", actual_after)

    current_state = {
        "kind": "observed_facts",
        "workspace_files": sorted(
            str(p.relative_to(WORKSPACE)).replace("\\", "/")
            for p in WORKSPACE.rglob("*")
            if p.is_file() and "__pycache__" not in str(p)
        ),
        "apply": apply_result,
        "tests": test_result,
        "errors": list(apply_result.get("errors") or [])
        + ([] if test_result is None or test_result.get("passed") else ["test_failed"]),
    }
    dump(run_dir / "current_state.json", current_state)

    # Phase 7
    recheck = classify_recheck(
        apply_result=apply_result,
        test_result=test_result,
        actual_after=actual_after,
        focus=focus,
        skipped_implementer=skipped,
    )
    dump(run_dir / "phase7_recheck.json", recheck)

    elapsed = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
    summary = {
        "experiment": "medium_task_reality_v0",
        "run_id": run_id,
        "parent_completion_gap_run": "20260909T023138Z",
        "parent_complete_treatment": "valid_in_local_gap_world",
        "cursor_role": "observer_harness",
        "game_code_author": "qwen3:14b_local_implementer" if not skipped else "none",
        "medium_task": medium.get("medium_task"),
        "gap": gap,
        "focus": {
            "minimum_focus": focus.get("minimum_focus"),
            "vertical_map": focus.get("vertical_map"),
            "horizontal_map": focus.get("horizontal_map"),
            "allowed_write": focus.get("allowed_write"),
        },
        "apply_applied": apply_result.get("applied"),
        "test_passed": None if test_result is None else test_result.get("passed"),
        "recheck": recheck.get("status"),
        "next_gap": recheck.get("next_gap"),
        "elapsed_s": elapsed,
        "stop": "one_pass_complete",
        "stage3_not_started": True,
    }
    dump(run_dir / "run.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
