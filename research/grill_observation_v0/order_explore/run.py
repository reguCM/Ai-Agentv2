"""Spec-order exploration. New run only. Does not touch prior Grill runs.

No Human/AI classification. No reverse conversion. No adoption gate.
Treat each recommendation as assumed_complete / provisional inside this run.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
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

from research.grill_observation_v0.ollama_call import call_local
from research.grill_observation_v0.parse import extract_json_object

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MAX_TURNS = 5
GOAL = "このPC環境で動く簡単なテトリスを作る"

SYSTEM = """あなたは Goal を仕様へ段階的に具体化する役です。
ここまでの項目は決まったものとして扱います。
次に決めるべき最も重要な項目を1つだけ選んでください。
その項目について有力な候補と推奨案、短い理由を出してください。
コードは書かない。人間の回答を作らない。JSON のみ返す。
既に assumed_complete にある項目を選び直さない。
"""

OUTPUT_SHAPE = {
    "item": {
        "id": "short_id",
        "title": "次に決める項目名",
        "why_now": "なぜ今これを決めるか",
    },
    "options": [
        {"id": "A", "label": "短い名前", "description": "この候補の内容"}
    ],
    "recommendation": {"id": "A", "reason": "短い理由"},
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def initial_state() -> dict[str, Any]:
    return {
        "goal": GOAL,
        "assumed_complete": [
            {
                "id": "impl_language",
                "title": "実装言語",
                "value": "Python",
                "status": "provisional",
                "note": "探索用の仮確定。正式 confirmed ではない。",
            },
            {
                "id": "game_library",
                "title": "ゲーム実装ライブラリ",
                "value": "Pygame",
                "status": "provisional",
                "note": "探索用の仮確定。正式 confirmed ではない。",
            },
        ],
    }


def build_user(state: dict[str, Any], turn_no: int) -> str:
    return "\n".join(
        [
            "# Goal",
            str(state.get("goal") or GOAL),
            "",
            "# ここまでの仮確定（assumed_complete / provisional）",
            "正式 confirmed ではない。この探索では決まったものとして扱う。",
            json.dumps(state.get("assumed_complete") or [], ensure_ascii=False, indent=2),
            "",
            f"# Turn {turn_no}",
            "ここまでの項目は決まったものとして扱います。",
            "現在のGoalと決定済み内容を踏まえて、",
            "次に決めるべき最も重要な項目を1つだけ選んでください。",
            "その項目について有力な候補と推奨案、短い理由を出してください。",
            "出力JSONの形:",
            json.dumps(OUTPUT_SHAPE, ensure_ascii=False, indent=2),
        ]
    )


def option_for_rec(parsed: dict[str, Any]) -> dict[str, Any] | None:
    rec = parsed.get("recommendation") if isinstance(parsed.get("recommendation"), dict) else {}
    rec_id = str(rec.get("id") or "")
    for opt in parsed.get("options") or []:
        if isinstance(opt, dict) and str(opt.get("id") or "") == rec_id:
            return opt
    return None


def apply_provisional(state: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state)
    item = parsed.get("item") if isinstance(parsed.get("item"), dict) else {}
    rec = parsed.get("recommendation") if isinstance(parsed.get("recommendation"), dict) else {}
    opt = option_for_rec(parsed) or {}
    value = opt.get("label") or rec.get("id") or ""
    next_state["assumed_complete"] = list(next_state.get("assumed_complete") or [])
    next_state["assumed_complete"].append(
        {
            "id": str(item.get("id") or f"turn_item"),
            "title": str(item.get("title") or item.get("id") or ""),
            "value": value,
            "option_id": rec.get("id"),
            "status": "provisional",
            "reason": rec.get("reason"),
            "note": "このRun内だけで仮に完了したものとして追加。",
        }
    )
    return next_state


def normalize(parsed: dict[str, Any] | None) -> dict[str, Any]:
    src = parsed or {}
    item = src.get("item") if isinstance(src.get("item"), dict) else {}
    rec = src.get("recommendation") if isinstance(src.get("recommendation"), dict) else {}
    options = []
    for opt in src.get("options") or []:
        if not isinstance(opt, dict):
            continue
        options.append(
            {
                "id": str(opt.get("id") or ""),
                "label": str(opt.get("label") or ""),
                "description": str(opt.get("description") or ""),
            }
        )
    return {
        "item": {
            "id": str(item.get("id") or ""),
            "title": str(item.get("title") or ""),
            "why_now": str(item.get("why_now") or ""),
        },
        "options": options,
        "recommendation": {
            "id": str(rec.get("id") or ""),
            "reason": str(rec.get("reason") or ""),
        },
    }


def order_lines(run: dict[str, Any]) -> list[str]:
    lines = [
        f"run_id: {run.get('run_id')}",
        f"goal: {run.get('goal')}",
        "initial provisional: Python / Pygame",
        "",
        "order:",
    ]
    initial = (run.get("initial_state") or {}).get("assumed_complete") or []
    n0 = len(initial)
    for i, item in enumerate((run.get("final_state") or {}).get("assumed_complete") or [], start=1):
        mark = "initial" if i <= n0 else f"T{i - n0}"
        lines.append(f"{i}. [{mark}] {item.get('title')}: {item.get('value')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grill spec-order exploration")
    parser.add_argument("--turns", type=int, default=MAX_TURNS)
    args = parser.parse_args(argv)
    turns = max(1, int(args.turns))

    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = _utc_stamp()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    state = initial_state()
    run: dict[str, Any] = {
        "experiment": "grill_order_explore_v0",
        "run_id": run_id,
        "parent_run_id": None,
        "model_id": model_id,
        "model": provider,
        "goal": GOAL,
        "max_turns": turns,
        "note": "assumed_complete/provisional only. Not formal confirmed. Isolated from prior Grill runs.",
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds") or profile.get("timeout_seconds"),
        },
        "initial_state": deepcopy(state),
        "turns": [],
        "final_state": None,
        "stopped": None,
    }
    _dump(run_dir / "run.json", run)

    for turn_no in range(1, turns + 1):
        state_before = deepcopy(state)
        user = build_user(state, turn_no)
        call = call_local(
            model=provider,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            num_ctx=int(profile.get("context_limit") or 8192),
            num_predict=int(profile.get("num_predict") or 2048),
            temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
            timeout_s=int(profile.get("hard_timeout_seconds") or 300),
            label=f"order_T{turn_no}",
        )
        obj, parse_err = extract_json_object(str(call.get("raw_text") or ""))
        parsed = normalize(obj)
        state_after = apply_provisional(state, parsed) if not (call.get("error") or parse_err) else deepcopy(state)
        rec_opt = option_for_rec(parsed) or {}
        turn = {
            "turn_no": turn_no,
            "state_before": state_before,
            "item": parsed.get("item"),
            "options": parsed.get("options"),
            "recommendation": parsed.get("recommendation"),
            "recommended_value": rec_opt.get("label"),
            "recommendation_reason": (parsed.get("recommendation") or {}).get("reason"),
            "raw_response": call.get("raw_text") or "",
            "elapsed_s": call.get("elapsed_s"),
            "error": call.get("error"),
            "parse_error": parse_err,
            "state_after": state_after,
            "prompt": {"system": SYSTEM, "user": user},
        }
        run["turns"].append(turn)
        (run_dir / f"turn_{turn_no}_raw.txt").write_text(str(turn["raw_response"]), encoding="utf-8")
        _dump(run_dir / f"turn_{turn_no}.json", turn)
        state = state_after
        run["final_state"] = deepcopy(state)
        run["stopped"] = f"after_T{turn_no}"
        _dump(run_dir / "run.json", run)
        if call.get("error") or parse_err:
            break

    run["final_state"] = deepcopy(state)
    lines = order_lines(run)
    (run_dir / "ORDER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _dump(run_dir / "run.json", run)
    print("\n".join(lines), flush=True)
    print(f"RUN {run_dir}", flush=True)
    print(f"STOPPED {run.get('stopped')}", flush=True)
    failed = any(t.get("error") or t.get("parse_error") for t in run.get("turns") or [])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
