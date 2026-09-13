"""Natural drill + exit observation.

Does not touch prior Grill runs.
Does not tell the LLM the turn cap or exit conditions.
Conversation history is not the memory; completed items in System are.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ollama import Client

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.system.config import get_llm_profile
from tools.system.model_registry import (
    get_pipeline_active_model_id,
    resolve_provider_model_name,
)

from research.grill_observation_v0.parse import extract_json_object

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MAX_TURNS = 20
GOAL = "簡単なテトリスを作る。"

# Standing rules only. Not repeated in the per-turn user message.
# Exit conditions / turn cap / routing are intentionally absent.
SYSTEM = """対象のGoal:
簡単なテトリスを作る。

原則:
1. 共通理解に達するまで、計画のあらゆる面を質問する。
2. 質問は1つずつ行い、各質問には推奨回答を付ける。
3. コードベースや環境から分かることはユーザーに聞かず、自分で調べる。
"""

# Observer-only. Never sent to the LLM.
EXIT_SPEECH = [
    r"主要な仕様.{0,12}(十分|揃)",
    r"十分(決まった|そろった|揃った)",
    r"もう.{0,12}(決める|決めるべき|質問する).{0,8}(ない|ありません)",
    r"新しく決める.{0,8}(ない|不要)",
    r"実装(に|へ)進(む|もう|め|み)",
    r"実装を始",
    r"コードを書き始",
    r"コードを書くべき",
    r"コード作成を始",
    r"これ以上.{0,12}(決ま|質問|仕様).{0,8}(ない|不要)",
    r"ready to implement",
    r"nothing (left|more) to (decide|ask)",
]
IMPL_INTERNAL = [
    r"ファイル構成",
    r"ディレクトリ構成",
    r"モジュール分割",
    r"クラス(設計|構成|分割)",
    r"関数(設計|分割|構成)",
    r"ソース(構成|分割)",
    r"パッケージ構成",
]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def message_content(resp: Any) -> str:
    msg = resp.get("message") if isinstance(resp, dict) else getattr(resp, "message", None)
    if isinstance(msg, dict):
        return str(msg.get("content") or "")
    return str(getattr(msg, "content", "") or "")


def call_freeform(
    *,
    model: str,
    messages: list[dict[str, str]],
    num_ctx: int,
    num_predict: int,
    temperature: float,
    timeout_s: int,
    label: str,
) -> dict[str, Any]:
    """No format=json, so exit speech is not forced into an item object."""
    client = Client(timeout=timeout_s)
    started = time.perf_counter()
    error = None
    resp = None
    stop = threading.Event()

    def heartbeat() -> None:
        while not stop.wait(15):
            elapsed = time.perf_counter() - started
            print(f"HEARTBEAT {label} elapsed_s={elapsed:.0f} timeout_s={timeout_s}", flush=True)

    hb = threading.Thread(target=heartbeat, daemon=True)
    hb.start()
    try:
        print(
            f"CALL {label} model={model} num_ctx={num_ctx} num_predict={num_predict} timeout_s={timeout_s}",
            flush=True,
        )
        resp = client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
            keep_alive="10m",
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"ERROR {label} {error}", flush=True)
    finally:
        stop.set()
    wall_s = round(time.perf_counter() - started, 3)
    raw = "" if resp is None else message_content(resp)
    print(f"DONE {label} wall_s={wall_s} error={error}", flush=True)
    return {"elapsed_s": wall_s, "error": error, "raw_text": raw}


def initial_completed() -> list[dict[str, Any]]:
    return [
        {"text": "Pythonで作る"},
        {"text": "Pygameを使う"},
    ]


def render_completed(items: list[dict[str, Any]]) -> str:
    lines = [str(it.get("text") or "").strip() for it in items]
    lines = [ln for ln in lines if ln]
    return "完了済み\n" + "\n".join(lines)


def build_user(items: list[dict[str, Any]]) -> str:
    return "次に決めた方がいいことは何ですか？\n\n" + render_completed(items)


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def find_patterns(text: str, patterns: list[str]) -> list[str]:
    hits: list[str] = []
    raw = str(text or "")
    for pat in patterns:
        if re.search(pat, raw, flags=re.I):
            hits.append(pat)
    return hits


def looks_like_code_dump(text: str) -> bool:
    raw = str(text or "")
    fenced = "```" in raw and raw.count("\n") >= 25
    many_defs = len(re.findall(r"^\s*(def|class)\s+", raw, flags=re.M)) >= 3
    return bool(fenced and "import pygame" in raw) or many_defs


def still_asking(raw: str, parsed: dict[str, Any]) -> bool:
    if str((parsed.get("item") or {}).get("title") or "").strip():
        return True
    if re.search(r"質問\s*[:：]", raw):
        return True
    if re.search(r"^###\s+", raw, flags=re.M):
        return True
    return False


def normalize_parsed(obj: dict[str, Any] | None) -> dict[str, Any]:
    src = obj or {}
    item = src.get("item") if isinstance(src.get("item"), dict) else {}
    rec = src.get("recommendation") if isinstance(src.get("recommendation"), dict) else {}
    options: list[dict[str, Any]] = []
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


def parse_response(raw: str) -> tuple[dict[str, Any], str | None]:
    obj, err = extract_json_object(raw)
    if obj:
        parsed = normalize_parsed(obj)
        if parsed["item"]["title"] or parsed["recommendation"]["id"] or parsed["options"]:
            return parsed, None
    return normalize_parsed({}), err or "unstructured"


def recommended_value(parsed: dict[str, Any]) -> str:
    rec = parsed.get("recommendation") or {}
    rec_id = str(rec.get("id") or "")
    for opt in parsed.get("options") or []:
        if str(opt.get("id") or "") == rec_id:
            return str(opt.get("label") or rec_id)
    return rec_id


def duplicate_of_completed(title: str, value: str, completed: list[dict[str, Any]]) -> bool:
    key = _norm(title)
    val = _norm(value)
    if not key and not val:
        return False
    for it in completed:
        text = _norm(it.get("text") or "")
        prev_title = _norm(it.get("title") or "")
        prev_val = _norm(it.get("value") or "")
        if key and (key == prev_title or key in text):
            if not val or val == prev_val or val in text:
                return True
    return False


def observer_stop_reason(
    *,
    raw: str,
    parsed: dict[str, Any],
    added: dict[str, Any] | None,
    completed_before: list[dict[str, Any]],
    previous_raw: str | None,
) -> str | None:
    """Never sent to the LLM. Used only to stop the experiment runner."""
    blob = raw + "\n" + json.dumps(parsed, ensure_ascii=False)
    title = str((parsed.get("item") or {}).get("title") or "")
    asking = still_asking(raw, parsed)
    if looks_like_code_dump(raw) and not asking:
        return "started_writing_code"
    speech = find_patterns(blob, EXIT_SPEECH)
    if speech and not asking:
        return "exit_speech:" + ",".join(speech[:3])
    internal = find_patterns(title, IMPL_INTERNAL)
    if internal and not asking:
        return "implementation_internal:" + ",".join(internal[:3])
    if added and duplicate_of_completed(
        str(added.get("title") or ""),
        str(added.get("value") or ""),
        completed_before,
    ):
        return "repeat_completed_item"
    if previous_raw and not added:
        a = _norm(previous_raw)[:800]
        b = _norm(raw)[:800]
        if a and a == b:
            return "repeat_same_raw"
    return None


def apply_recommendation(
    completed: list[dict[str, Any]], parsed: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    item = parsed.get("item") or {}
    title = str(item.get("title") or "").strip()
    value = recommended_value(parsed).strip()
    if not title and not value:
        return deepcopy(completed), None
    rec = parsed.get("recommendation") or {}
    added = {
        "title": title,
        "value": value,
        "option_id": rec.get("id"),
        "reason": rec.get("reason"),
        "text": f"{title}: {value}" if title and value else (title or value),
    }
    nxt = deepcopy(completed)
    nxt.append(added)
    return nxt, added


def turn_line(turn: dict[str, Any]) -> str:
    n = turn.get("turn_no")
    added = turn.get("added") or {}
    item = (turn.get("parsed") or {}).get("item") or {}
    title = added.get("title") or item.get("title") or ""
    value = added.get("value") or ""
    stop = turn.get("observer_stop_reason")
    if title and value:
        core = f"{title}: {value}"
    elif title:
        core = title
    else:
        core = "(構造化項目なし)"
    if stop:
        return f"T{n}  {core}  [observer_stop={stop}]"
    return f"T{n}  {core}"


def write_turn_list(run_dir: Path, run: dict[str, Any]) -> None:
    lines = [f"run_id: {run.get('run_id')}", f"goal: {GOAL}", f"stopped: {run.get('stopped')}", "", "turns:"]
    for t in run.get("turns") or []:
        lines.append(turn_line(t))
    (run_dir / "TURN_LIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    run_id = _utc_stamp()
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshots = run_dir / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)

    completed = initial_completed()
    run: dict[str, Any] = {
        "experiment": "grill_natural_exit_v0",
        "run_id": run_id,
        "model_id": model_id,
        "model": provider,
        "goal": GOAL,
        "max_turns_hidden_from_llm": MAX_TURNS,
        "system_prompt": SYSTEM,
        "initial_completed": deepcopy(completed),
        "turns": [],
        "stopped": None,
        "observer_stop_reason": None,
        "note": "Independent run. Prior Grill runs are not modified. History is not memory.",
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds") or profile.get("timeout_seconds"),
        },
    }
    (run_dir / "SYSTEM.txt").write_text(SYSTEM, encoding="utf-8")
    _dump(snapshots / "completed_before_T1.json", completed)
    _dump(run_dir / "run.json", run)

    for turn_no in range(1, MAX_TURNS + 1):
        before = deepcopy(completed)
        user = build_user(before)
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
            label=f"exit_T{turn_no}",
        )
        raw = str(call.get("raw_text") or "")
        parsed, parse_error = parse_response(raw)
        after, added = apply_recommendation(before, parsed)
        prev_raw = None
        if run["turns"]:
            prev_raw = str(run["turns"][-1].get("raw_response") or "")
        stop = None
        if not call.get("error"):
            stop = observer_stop_reason(
                raw=raw,
                parsed=parsed,
                added=added,
                completed_before=before,
                previous_raw=prev_raw,
            )
        if added and stop != "repeat_completed_item":
            completed = after
        elif added and stop == "repeat_completed_item":
            completed = before
        turn = {
            "turn_no": turn_no,
            "completed_before": before,
            "user_input": user,
            "raw_response": raw,
            "elapsed_s": call.get("elapsed_s"),
            "error": call.get("error"),
            "parse_error": parse_error,
            "parsed": parsed,
            "item": parsed.get("item"),
            "options": parsed.get("options"),
            "recommendation": parsed.get("recommendation"),
            "added": added,
            "completed_after": deepcopy(completed),
            "observer_stop_reason": stop,
        }
        run["turns"].append(turn)
        (run_dir / f"turn_{turn_no}_raw.txt").write_text(raw, encoding="utf-8")
        (run_dir / f"turn_{turn_no}_user.txt").write_text(user, encoding="utf-8")
        _dump(run_dir / f"turn_{turn_no}.json", turn)
        _dump(snapshots / f"completed_after_T{turn_no}.json", completed)
        if stop:
            run["stopped"] = f"after_T{turn_no}"
            run["observer_stop_reason"] = stop
        elif call.get("error"):
            run["stopped"] = f"error_T{turn_no}"
            run["observer_stop_reason"] = str(call.get("error"))
        else:
            run["stopped"] = f"after_T{turn_no}"
        _dump(run_dir / "run.json", run)
        write_turn_list(run_dir, run)
        print(turn_line(turn), flush=True)
        if stop or call.get("error"):
            break
    else:
        run["stopped"] = "turn_cap_20"
        run["observer_stop_reason"] = "hidden_turn_cap"
        _dump(run_dir / "run.json", run)
        write_turn_list(run_dir, run)

    print(f"RUN {run_dir}", flush=True)
    print(f"STOPPED {run.get('stopped')} reason={run.get('observer_stop_reason')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
