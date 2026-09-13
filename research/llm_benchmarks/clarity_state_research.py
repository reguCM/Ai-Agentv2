"""
③ STATE → Research ベンチ。unittest ではない。

Clarity 問答で機械が作った STATE を、最初から存在する STATE ではなく
会話由来として Research / Judge に渡す。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.clarity_state_classify import (
    AMBIGUOUS_VALUE_MATERIALS,
    inspect_meaning_from_state,
    inspect_not_overwritten,
    inspect_state_in_research_messages,
    inspect_user_state,
    run_scripted_handoff,
)
from research.llm_benchmarks.persistence_classify import classify_status_unit
from tools.ai.llm.adapter import build_state_query_messages, retry_extra
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.timing import Timing


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_HANDOFF_REPEAT") or 3)
RESULTS_PATH = "research/llm_benchmarks/clarity_state_research_results.json"


def extract_json_object(text):
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(stripped[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def ask_json(materials, profile, *, state):
    messages = build_state_query_messages(materials, profile=profile, state=state)
    try:
        response = chat(model=profile["model"], messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_state_query_messages(
            materials, extra=retry_extra(profile), profile=profile, state=state
        )
        try:
            response = chat(model=profile["model"], messages=messages)
            text = response.message.content
        except LLMTimeoutError as exc:
            return None, "timeout", str(exc)
        payload = extract_json_object(text)
    if payload is None:
        return None, "no_json", text
    return payload, None, text


def haystack_from(payload, text):
    parts = [text or ""]
    if isinstance(payload, dict):
        parts.append(str(payload.get("answer") or ""))
        parts.append(str(payload.get("reason") or ""))
        parts.extend(str(item) for item in payload.get("used_state_keys") or [])
    return "\n".join(parts)


def main():
    print(
        f"handoff  repeat={REPEAT}  profile={PROFILE_ID}  model={MODEL}"
    )
    handoff = run_scripted_handoff()
    state = handoff["state"]
    user_state = inspect_user_state(state)
    in_research = inspect_state_in_research_messages(state)
    not_overwritten = inspect_not_overwritten(state)
    print(
        f"1 user_state={user_state['ok']}  "
        f"2 in_research={in_research['ok']}  "
        f"4 not_overwritten={not_overwritten['ok']}"
    )
    meaning_rows = []
    try:
        for index in range(1, REPEAT + 1):
            with Timing() as clock:
                payload, error, text = ask_json(
                    AMBIGUOUS_VALUE_MATERIALS, PROFILE, state=state
                )
            labels = classify_status_unit(
                haystack_from(payload, text), state_present=True
            )
            held = inspect_meaning_from_state(
                payload if isinstance(payload, dict) else {}, labels
            )
            ok = (not error) and held["ok"]
            mark = "PASS" if ok else "FAIL"
            print(
                f"{mark}  meaning  {index}/{REPEAT}  "
                f"memory={held['memory']}  "
                f"unit={held['unit']}  "
                f"why={labels.get('reason_class')}  "
                f"state_based={held['state_based']}  "
                f"keys={held['used_state_keys']}  "
                f"{clock.snapshot().get('total_seconds')}s"
            )
            if isinstance(payload, dict):
                print(f"  answer: {payload.get('answer')}")
                print(f"  reason: {payload.get('reason')}")
            meaning_rows.append(
                {
                    "n": index,
                    "ok": ok,
                    "pass": ok,
                    "error": error,
                    "labels": labels,
                    "held": held,
                    "answer": None if not isinstance(payload, dict) else payload.get("answer"),
                    "reason": None if not isinstance(payload, dict) else payload.get("reason"),
                    "timing": clock.snapshot(),
                }
            )
    finally:
        stop_model(MODEL)

    meaning_ok = all(item["ok"] for item in meaning_rows) and bool(meaning_rows)
    passed = (
        user_state["ok"]
        and in_research["ok"]
        and meaning_ok
        and not_overwritten["ok"]
    )
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Clarity問答由来の STATE を Research へ。最初からSTATEがあるベンチではない。",
        "profile": PROFILE_ID,
        "model": MODEL,
        "pass": passed,
        "ok": passed,
        "user_state": user_state,
        "in_research": in_research,
        "meaning": {"ok": meaning_ok, "trials": meaning_rows},
        "not_overwritten": {
            "ok": not_overwritten["ok"],
            "checks": not_overwritten["checks"],
        },
        "state": state.snapshot(),
    }
    path = Path(RESULTS_PATH)
    payload = {"runs": []}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("runs", [])
    payload["runs"].append(entry)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"pass={passed}  "
        f"user={user_state['ok']}  research={in_research['ok']}  "
        f"meaning={meaning_ok}  locked={not_overwritten['ok']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        raise SystemExit(1)
    finally:
        stop_model(MODEL)
