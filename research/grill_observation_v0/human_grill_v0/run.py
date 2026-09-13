"""Human Grill: extract what the user wants. Independent run.

Does not touch prior Grill runs. Does not answer as the human.
Conversation history is not memory; System-stored human specs are.
"""
from __future__ import annotations

import argparse
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
GOAL = "このPC環境で動くテトリスを作りたい。"

SYSTEM = """対象のGoal:
このPC環境で動くテトリスを作りたい。

これは、どうコードを書くかではなく、ユーザーがどんな完成品を望んでいるかを確認するための対話です。

原則:
1. ユーザーがどんな完成品を望んでいるかについて、共通理解に達するまで質問する。
2. 質問は1つずつ行い、各質問には有力な選択肢と推奨回答を付ける。
3. 現在のPC環境やコードベースから分かることはユーザーに聞かず、自分で調べる。
"""

# Observer-only. Never sent to the LLM.
EXIT_SPEECH = [
    r"作り始められる",
    r"作り始めて(よい|良い|大丈夫)",
    r"実装(に|へ)進(む|もう|め|み)",
    r"実装を始",
    r"必要な仕様.{0,12}(十分|揃)",
    r"十分決まった",
    r"残りは実装",
    r"追加質問.{0,12}(微調整|好み)",
    r"これ以上.{0,8}(聞か|質問).{0,8}(ない|不要)",
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


def normalize_options(raw_opts: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for opt in raw_opts or []:
        if not isinstance(opt, dict):
            continue
        out.append(
            {
                "id": str(opt.get("id") or ""),
                "label": str(opt.get("label") or ""),
                "description": str(opt.get("description") or ""),
            }
        )
    return out


def parse_markdown_question(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    headings = re.findall(r"^#{2,3}\s+\**(.+?)\**\s*$", text, flags=re.M)
    questions = re.findall(r"\*\*質問:\*\*\s*(.+?)(?=\*\*推奨|\n\s*[-*]|\Z)", text, flags=re.S)
    if len(headings) > 1 or len(re.findall(r"\*\*質問:\*\*", text)) > 1:
        return {
            "item": {"id": "", "title": "", "why_now": ""},
            "question": "",
            "options": [],
            "recommendation": {"id": "", "reason": ""},
            "multi_question": True,
        }
    item_title = ""
    m_title = re.search(r"(?:決める項目|今回決めること|項目)\s*[:：]\s*(.+)", text)
    if m_title:
        item_title = m_title.group(1).strip()
    elif headings:
        item_title = headings[0].strip()
    q = ""
    m_q = re.search(r"(?:質問|Q)\s*[:：]\s*(.+?)(?:\n\s*\n|\n\[A\]|\nA[\.．]|\*\*推奨)", text, flags=re.S)
    if m_q:
        q = m_q.group(1).strip()
    options: list[dict[str, str]] = []
    for m in re.finditer(
        r"(?:\[([A-Z0-9]+)\]|([A-Z])[\.．、:：])\s*(.+?)(?=\n(?:\[[A-Z0-9]+\]|[A-Z][\.．、:：]|推奨)|\Z)",
        text,
        flags=re.S,
    ):
        oid = (m.group(1) or m.group(2) or "").strip()
        body = re.sub(r"\s+", " ", m.group(3)).strip()
        if oid:
            options.append({"id": oid, "label": body, "description": ""})
    rec_id = ""
    rec_reason = ""
    m_rec = re.search(r"推奨(?:回答)?\s*[:：]?\s*([A-Z0-9])?\s*(.*)", text)
    if m_rec:
        rec_id = (m_rec.group(1) or "").strip()
        rec_reason = (m_rec.group(2) or "").strip()
    if not (item_title or q or options):
        return None
    return {
        "item": {"id": "", "title": item_title, "why_now": ""},
        "question": q,
        "options": options,
        "recommendation": {"id": rec_id, "reason": rec_reason},
        "multi_question": False,
    }


def parse_llm(raw: str) -> tuple[dict[str, Any], str | None]:
    obj, err = extract_json_object(raw)
    if isinstance(obj, dict) and (
        obj.get("item") or obj.get("question") or obj.get("options") or obj.get("recommendation")
    ):
        item = obj.get("item") if isinstance(obj.get("item"), dict) else {}
        rec = obj.get("recommendation") if isinstance(obj.get("recommendation"), dict) else {}
        parsed = {
            "item": {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "why_now": str(item.get("why_now") or ""),
            },
            "question": str(obj.get("question") or ""),
            "options": normalize_options(obj.get("options")),
            "recommendation": {
                "id": str(rec.get("id") or ""),
                "reason": str(rec.get("reason") or ""),
            },
            "multi_question": False,
        }
        return parsed, None
    md = parse_markdown_question(raw)
    if md:
        return md, None if not md.get("multi_question") else "multi_question"
    return {
        "item": {"id": "", "title": "", "why_now": ""},
        "question": "",
        "options": [],
        "recommendation": {"id": "", "reason": ""},
        "multi_question": False,
    }, err or "unstructured"


def option_by_id(parsed: dict[str, Any], oid: str) -> dict[str, str] | None:
    for opt in parsed.get("options") or []:
        if str(opt.get("id") or "").upper() == str(oid).upper():
            return opt
    return None


def recommended_option(parsed: dict[str, Any]) -> dict[str, str] | None:
    rec = parsed.get("recommendation") or {}
    return option_by_id(parsed, str(rec.get("id") or ""))


def spec_sentence(title: str, value: str) -> str:
    title = str(title or "").strip()
    value = str(value or "").strip()
    if title and value:
        if value.endswith("。"):
            return value
        return f"{title}は、{value}。"
    return value or title


def is_delegate(answer: str) -> bool:
    t = re.sub(r"\s+", "", answer)
    return t in {"任せる", "おまかせ", "お任せ", "お任せします", "任せます", "AIに任せる"}


def is_accept_rec(answer: str) -> bool:
    t = re.sub(r"\s+", "", answer)
    return t in {"それでいい", "それで良い", "それでOK", "それでおk", "推奨で", "推奨どおり", "推奨通り", "OK", "おk", "いいよ", "それで"}


def is_unknown(answer: str) -> bool:
    t = re.sub(r"\s+", "", answer)
    return t in {"分からない", "わからない", "不明", "まだ分からない"}


def interpret_answer(answer: str, parsed: dict[str, Any]) -> dict[str, Any]:
    raw = str(answer or "").strip()
    title = str((parsed.get("item") or {}).get("title") or "").strip()
    rec_opt = recommended_option(parsed)
    rec = parsed.get("recommendation") or {}
    rec_label = (rec_opt or {}).get("label") or rec.get("reason") or rec.get("id") or ""

    m_letter = re.match(r"^([A-Za-z])(?:がいい|が良い|で|にする)?$", re.sub(r"\s+", "", raw))
    chosen = None
    if m_letter:
        chosen = option_by_id(parsed, m_letter.group(1))
    else:
        for opt in parsed.get("options") or []:
            label = str(opt.get("label") or "")
            if label and (raw == label or label in raw):
                chosen = opt
                break

    if is_delegate(raw):
        value = rec_label or "AIに任せる"
        return {
            "kind": "delegate",
            "human_text": spec_sentence(title, "AIに任せる") if title else "この項目はAIに任せる。",
            "ai_provisional": spec_sentence(title, value) if value else "",
            "raw": raw,
        }
    if is_unknown(raw):
        return {
            "kind": "unknown",
            "human_text": spec_sentence(title, "まだ分からない") if title else "この項目はまだ分からない。",
            "ai_provisional": "",
            "raw": raw,
        }
    if chosen:
        label = chosen.get("label") or chosen.get("id") or raw
        desc = chosen.get("description") or ""
        value = desc if desc and len(desc) > len(label) else label
        return {
            "kind": "human_choice",
            "human_text": spec_sentence(title, value),
            "ai_provisional": "",
            "raw": raw,
        }
    if is_accept_rec(raw):
        value = rec_label or rec.get("reason") or "推奨案を採用"
        return {
            "kind": "human_accept_recommendation",
            "human_text": spec_sentence(title, value),
            "ai_provisional": "",
            "raw": raw,
        }
    return {
        "kind": "human_freeform",
        "human_text": spec_sentence(title, raw) if title else raw,
        "ai_provisional": "",
        "raw": raw,
    }


def completed_for_llm(specs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for spec in specs:
        if spec.get("kind") == "unknown":
            continue
        text = str(spec.get("human_text") or "").strip()
        if text:
            lines.append(text)
    if not lines:
        return ""
    return "完了済み\n" + "\n".join(lines)


def build_user(specs: list[dict[str, Any]]) -> str:
    body = completed_for_llm(specs)
    if not body:
        return "テトリスを作りたいです。\n次に決めた方がいいことは何ですか？"
    return "次に決めた方がいいことは何ですか？\n\n" + body


def find_exit(raw: str) -> str | None:
    text = str(raw or "")
    hits = [p for p in EXIT_SPEECH if re.search(p, text)]
    if hits:
        return hits[0]
    return None


def render_human_view(run: dict[str, Any]) -> str:
    turns = run.get("turns") or []
    pending = next((t for t in turns if t.get("awaiting_human")), None)
    specs = run.get("human_specs") or []
    lines = [
        "[Goal]",
        GOAL,
        "",
        "[人間仕様]",
    ]
    if not specs:
        lines.append("(まだなし)")
    for spec in specs:
        src = spec.get("kind")
        extra = ""
        if src == "delegate":
            extra = " （AIに任せる。仮: " + str(spec.get("ai_provisional") or "") + "）"
        lines.append("- " + str(spec.get("human_text") or "") + extra)
    lines.append("")
    if pending:
        parsed = pending.get("parsed") or {}
        rec = parsed.get("recommendation") or {}
        lines += [
            f"[T{pending.get('turn_no')} 質問]",
            str(parsed.get("question") or parsed.get("item", {}).get("title") or ""),
            "",
            "[選択肢]",
        ]
        opts = parsed.get("options") or []
        if not opts:
            lines.append("(構造化なし。raw を参照)")
        for opt in opts:
            lines.append(f"[{opt.get('id')}] {opt.get('label')}")
            if opt.get("description"):
                lines.append(str(opt.get("description")))
        lines += [
            "",
            "[推奨]",
            str(rec.get("id") or ""),
            str(rec.get("reason") or ""),
            "",
        ]
        if pending.get("natural_exit_hint"):
            lines += ["[自然出口の兆し]", str(pending.get("natural_exit_hint")), ""]
        lines.append(str(pending.get("raw_response") or ""))
    elif run.get("natural_exit_turn"):
        lines += [
            f"[自然出口] T{run.get('natural_exit_turn')}",
            str(run.get("natural_exit_hint") or ""),
        ]
    return "\n".join(lines).rstrip() + "\n"


def save_run(run_dir: Path, run: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _dump(run_dir / "run.json", run)
    (run_dir / "HUMAN_VIEW.md").write_text(render_human_view(run), encoding="utf-8")
    specs = run.get("human_specs") or []
    human_lines = ["人間仕様", ""]
    for spec in specs:
        mark = "AI委任" if spec.get("kind") == "delegate" else "人間"
        human_lines.append(f"- [{mark}] {spec.get('human_text')}")
        if spec.get("kind") == "delegate" and spec.get("ai_provisional"):
            human_lines.append(f"  仮採用: {spec.get('ai_provisional')}")
    (run_dir / "HUMAN_SPECS.md").write_text("\n".join(human_lines) + "\n", encoding="utf-8")


def new_run() -> dict[str, Any]:
    model_id = get_pipeline_active_model_id() or "qwen3_14b"
    provider = resolve_provider_model_name(model_id)
    profile = get_llm_profile(model_id)
    return {
        "experiment": "human_grill_natural_exit_v0",
        "run_id": _utc_stamp(),
        "model_id": model_id,
        "model": provider,
        "goal": GOAL,
        "max_turns_hidden_from_llm": MAX_TURNS,
        "system_prompt": SYSTEM,
        "human_specs": [],
        "turns": [],
        "status": "ready",
        "natural_exit_turn": None,
        "natural_exit_hint": None,
        "stopped": None,
        "profile": {
            "context_limit": profile.get("context_limit"),
            "num_predict": profile.get("num_predict"),
            "temperature": profile.get("temperature"),
            "hard_timeout_seconds": profile.get("hard_timeout_seconds") or profile.get("timeout_seconds"),
        },
        "note": "Independent Human Grill. Prior runs unchanged. LLM must not answer as human.",
    }


def ask_llm(run: dict[str, Any]) -> dict[str, Any]:
    n = len(run.get("turns") or []) + 1
    if n > MAX_TURNS:
        run["stopped"] = "turn_cap_20"
        run["status"] = "stopped_cap"
        return {}
    user = build_user(run.get("human_specs") or [])
    profile = run.get("profile") or {}
    call = call_freeform(
        model=str(run["model"]),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        num_ctx=int(profile.get("context_limit") or 8192),
        num_predict=int(profile.get("num_predict") or 2048),
        temperature=float(profile.get("temperature") if profile.get("temperature") is not None else 0),
        timeout_s=int(profile.get("hard_timeout_seconds") or 300),
        label=f"human_T{n}",
    )
    parsed, parse_err = parse_llm(str(call.get("raw_text") or ""))
    hint = find_exit(str(call.get("raw_text") or ""))
    turn = {
        "turn_no": n,
        "completed_before": deepcopy(run.get("human_specs") or []),
        "user_input": user,
        "raw_response": call.get("raw_text") or "",
        "elapsed_s": call.get("elapsed_s"),
        "error": call.get("error"),
        "parse_error": parse_err,
        "parsed": parsed,
        "awaiting_human": True,
        "human_answer": None,
        "added_spec": None,
        "natural_exit_hint": hint,
    }
    run["turns"].append(turn)
    run["status"] = "awaiting_human"
    if hint and not run.get("natural_exit_turn"):
        run["natural_exit_turn"] = n
        run["natural_exit_hint"] = hint
    return turn


def apply_human_answer(run: dict[str, Any], answer: str) -> dict[str, Any]:
    turns = run.get("turns") or []
    pending = next((t for t in turns if t.get("awaiting_human")), None)
    if pending is None:
        raise RuntimeError("no pending human question")
    interpreted = interpret_answer(answer, pending.get("parsed") or {})
    spec = {
        "from_turn": pending.get("turn_no"),
        "item_title": str(((pending.get("parsed") or {}).get("item") or {}).get("title") or ""),
        "kind": interpreted["kind"],
        "human_text": interpreted["human_text"],
        "ai_provisional": interpreted.get("ai_provisional") or "",
        "raw_answer": interpreted["raw"],
        "decided_by": "AI" if interpreted["kind"] == "delegate" else "human",
    }
    pending["awaiting_human"] = False
    pending["human_answer"] = interpreted
    pending["added_spec"] = spec
    run["human_specs"] = list(run.get("human_specs") or [])
    if interpreted["kind"] != "unknown":
        run["human_specs"].append(spec)
    run["status"] = "ready_for_next"
    return spec


def write_turn_files(run_dir: Path, turn: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    n = turn.get("turn_no")
    (run_dir / f"turn_{n}_raw.txt").write_text(str(turn.get("raw_response") or ""), encoding="utf-8")
    (run_dir / f"turn_{n}_user.txt").write_text(str(turn.get("user_input") or ""), encoding="utf-8")
    _dump(run_dir / f"turn_{n}.json", turn)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human Grill natural-exit experiment")
    parser.add_argument("--new", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--answer")
    parser.add_argument("--ask-next", action="store_true")
    args = parser.parse_args(argv)
    RUNS.mkdir(parents=True, exist_ok=True)

    if args.new:
        run = new_run()
        run_dir = RUNS / str(run["run_id"])
        run_dir.mkdir(parents=True, exist_ok=True)
        turn = ask_llm(run)
        write_turn_files(run_dir, turn)
        save_run(run_dir, run)
        print(render_human_view(run), flush=True)
        print(f"RUN {run_dir}", flush=True)
        print("STOPPED awaiting human. Do not auto-answer.", flush=True)
        return 1 if turn.get("error") else 0

    if not args.run_id:
        parser.error("use --new or --run-id")
    run_dir = RUNS / args.run_id
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if args.answer is None:
        parser.error("--answer is required unless --new")
    spec = apply_human_answer(run, args.answer)
    save_run(run_dir, run)
    print("saved: " + str(spec.get("human_text")), flush=True)
    if run.get("natural_exit_turn") and not args.ask_next:
        run["stopped"] = f"natural_exit_T{run['natural_exit_turn']}"
        save_run(run_dir, run)
        print("natural exit already recorded; not asking next unless --ask-next", flush=True)
        return 0
    if not args.ask_next:
        print("not asking next unless --ask-next", flush=True)
        return 0
    if len(run.get("turns") or []) >= MAX_TURNS:
        run["stopped"] = "turn_cap_20"
        run["status"] = "stopped_cap"
        save_run(run_dir, run)
        print("STOPPED turn cap", flush=True)
        return 0
    turn = ask_llm(run)
    write_turn_files(run_dir, turn)
    save_run(run_dir, run)
    print(render_human_view(run), flush=True)
    print(f"RUN {run_dir}", flush=True)
    print("STOPPED awaiting human.", flush=True)
    return 1 if turn.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
