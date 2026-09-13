"""Grill observation v0 runner.

Experiment only. Does not call production llm.chat.
Does not modify Production Chat UI.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.display import render_turn
from research.grill_observation_v0.ollama_call import call_local
from research.grill_observation_v0.parse import extract_json_object, normalize_turn
from research.grill_observation_v0.prompts import SYSTEM, build_user
from research.grill_observation_v0.schema import apply_choice, empty_spec

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"

GOAL = (
    "このPC環境で動く、簡単なテトリスを作りたい。"
    "適切な実現方法・技術的な候補はAI側で考えてください。"
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def env_facts() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "workspace": "AI-Agent development worktree (not a blank game project)",
        "local_llm": "Ollama is used by this experiment runner",
        "note": "A simple Tetris that runs on this PC. Do not ask OS/runtime facts already listed.",
    }


def load_run(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def save_run(run_dir: Path, run: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _dump(run_dir / "run.json", run)
    turns = run.get("turns") or []
    if turns:
        last = turns[-1]
        view = render_turn(last.get("parsed") or {}, last.get("spec_state") or run.get("spec_state") or {})
        (run_dir / "HUMAN_VIEW.md").write_text(view, encoding="utf-8")
        (run_dir / f"turn_{last.get('n')}_raw.txt").write_text(
            str((last.get("raw_response") or "")), encoding="utf-8"
        )


def new_run(goal: str) -> dict[str, Any]:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = _utc_stamp()
    return {
        "experiment": "grill_observation_v0",
        "run_id": run_id,
        "status": "ready",
        "model_id": model_id,
        "model": provider,
        "goal": goal,
        "env_facts": env_facts(),
        "spec_state": empty_spec(goal),
        "turns": [],
        "awaiting_human": False,
        "stopped": None,
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds") or profile.get("timeout_seconds"),
        },
        "note": "Experiment run. Isolated from production chat logs.",
    }


def ask_one(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("awaiting_human"):
        raise RuntimeError("human answer pending; do not ask the next question")
    n = len(run.get("turns") or []) + 1
    spec = run.get("spec_state") or empty_spec(str(run.get("goal") or ""))
    user = build_user(goal=str(run["goal"]), spec=spec, env_facts=run.get("env_facts") or {}, turn=n)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]
    profile = run.get("profile") or {}
    call = call_local(
        model=str(run["model"]),
        messages=messages,
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label=f"Q{n}",
    )
    obj, parse_err = extract_json_object(str(call.get("raw_text") or ""))
    parsed = normalize_turn(obj)
    llm_spec = parsed.get("spec_state") or {}
    merged_spec = {
        "goal": llm_spec.get("goal") or spec.get("goal"),
        "confirmed": llm_spec.get("confirmed") or spec.get("confirmed") or [],
        "assumptions": llm_spec.get("assumptions") or spec.get("assumptions") or [],
        "unresolved": llm_spec.get("unresolved") or spec.get("unresolved") or [],
        "delegated": llm_spec.get("delegated") or spec.get("delegated") or [],
    }
    parsed["spec_state"] = merged_spec
    turn = {
        "n": n,
        "prompt": {"system": SYSTEM, "user": user},
        "raw_response": call.get("raw_text") or "",
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "parse_error": parse_err,
        "parsed": parsed,
        "spec_state": merged_spec,
    }
    run["turns"].append(turn)
    run["spec_state"] = merged_spec
    run["awaiting_human"] = True
    run["status"] = "awaiting_human"
    run["stopped"] = f"after_Q{n}"
    return turn


def apply_answer(run: dict[str, Any], answer: str) -> dict[str, Any]:
    if not run.get("awaiting_human"):
        raise RuntimeError("no pending question")
    turns = run.get("turns") or []
    last = turns[-1]
    parsed = last.get("parsed") or {}
    options = parsed.get("options") or []
    raw = answer.strip()
    chosen = None
    for opt in options:
        if raw.upper() == str(opt.get("id") or "").upper() or raw == str(opt.get("label") or ""):
            chosen = opt
            break
    if chosen is None:
        chosen = {"id": raw, "label": raw, "description": "freeform human answer"}
    focus = parsed.get("focus_item") or {}
    new_spec = apply_choice(
        run.get("spec_state") or empty_spec(str(run.get("goal") or "")),
        focus_id=str(focus.get("id") or f"q{last.get('n')}"),
        focus_title=str(focus.get("title") or ""),
        choice=chosen,
        human_raw=raw,
    )
    last["human_answer"] = {"raw": raw, "matched": chosen}
    run["spec_state"] = new_spec
    run["awaiting_human"] = False
    run["status"] = "ready_for_reeval"
    return new_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grill observation v0")
    parser.add_argument("--new", action="store_true", help="start a new run and ask Q1 only")
    parser.add_argument("--run-id", help="existing run id")
    parser.add_argument("--answer", help="human answer for the pending question (do not use on first Q1 run)")
    parser.add_argument("--ask-next", action="store_true", help="after an answer, ask the next question")
    args = parser.parse_args(argv)

    RUNS.mkdir(parents=True, exist_ok=True)

    if args.new:
        run = new_run(GOAL)
        run_dir = RUNS / run["run_id"]
        turn = ask_one(run)
        save_run(run_dir, run)
        print(render_turn(turn.get("parsed") or {}, turn.get("spec_state") or {}), flush=True)
        print(f"RUN {run_dir}", flush=True)
        print("STOPPED after Q1. Do not auto-answer. Do not ask Q2.", flush=True)
        return 1 if turn.get("error") or turn.get("parse_error") else 0

    if not args.run_id:
        parser.error("use --new or --run-id")
    run_dir = RUNS / args.run_id
    run = load_run(run_dir)
    if args.answer:
        apply_answer(run, args.answer)
        save_run(run_dir, run)
        print("recorded human answer; spec updated. not asking next unless --ask-next", flush=True)
        if not args.ask_next:
            return 0
    if args.ask_next:
        turn = ask_one(run)
        save_run(run_dir, run)
        print(render_turn(turn.get("parsed") or {}, turn.get("spec_state") or {}), flush=True)
        print(f"RUN {run_dir}", flush=True)
        return 1 if turn.get("error") or turn.get("parse_error") else 0
    parser.error("nothing to do")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
