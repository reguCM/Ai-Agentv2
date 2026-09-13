"""
同じ Judge 材料を何度か呼び、誤判定の再現率を見る。
unittest ではない。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from tools.ai.llm.adapter import build_research_judge_messages, retry_extra
from tools.ai.tool_builder.research_judge import (
    create_research_judgment,
    normalize_judgment,
)
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.timing import Timing, stage
from tools.system.llm_failure_memory import load_environment_case


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_JUDGE_REPEAT") or 5)
CASE_ID = os.environ.get("AI_AGENT_JUDGE_CASE") or "judge_status_vs_usage"
RESULTS_PATH = "research/llm_benchmarks/judge_repeat_results.json"


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


def ask_json(materials):
    messages = build_research_judge_messages(materials)
    try:
        response = chat(model=MODEL, messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_research_judge_messages(materials, extra=retry_extra())
        try:
            response = chat(model=MODEL, messages=messages)
            text = response.message.content
        except LLMTimeoutError as exc:
            return None, "timeout", str(exc)
        payload = extract_json_object(text)
    if payload is None:
        return None, "no_json", text
    return payload, None, text


def classify(judgment):
    if judgment.get("satisfies_request"):
        return "accept"
    reason = str(judgment.get("reason") or "")
    missing = " ".join(judgment.get("missing") or [])
    joined = reason + " " + missing
    if any(
        token in joined
        for token in ("状態コード", "success", "error", "成功フラグ", "status'形式")
    ):
        return "reject_status_as_code"
    return "reject"


def main():
    case = load_environment_case(CASE_ID)
    if not case:
        raise SystemExit(f"case がない: {CASE_ID}")
    materials = create_research_judgment(
        case["request"],
        case.get("proposal") or {"output": ["status"]},
        case.get("research_result") or {},
    )
    trials = []
    for index in range(1, REPEAT + 1):
        with Timing() as clock:
            with stage("judge"):
                payload, error, text = ask_json(materials)
                judgment = normalize_judgment(payload)
                if error:
                    judgment["error"] = error
            label = "error" if error else classify(judgment)
            trials.append(
                {
                    "n": index,
                    "label": label,
                    "satisfies_request": judgment.get("satisfies_request"),
                    "reason": judgment.get("reason"),
                    "missing": judgment.get("missing"),
                    "error": error,
                    "llm_text": text,
                    "timing": clock.snapshot(),
                }
            )
        mark = "ACCEPT" if label == "accept" else "REJECT"
        print(f"{index}/{REPEAT}  {mark}  {label}")
        print(f"  reason: {judgment.get('reason')}")
        print(f"  missing: {judgment.get('missing')}")
        print(f"  timing: {(trials[-1].get('timing') or {}).get('total_seconds')}s")

    counts = {}
    for item in trials:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    accept = counts.get("accept", 0)
    reject = REPEAT - accept
    print(f"accept={accept}/{REPEAT}  reject={reject}/{REPEAT}  counts={counts}")

    payload = {
        "note": "同じ Judge 材料の再現観察。契約は変えていない。",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case": CASE_ID,
        "profile": PROFILE_ID,
        "model": MODEL,
        "temperature": PROFILE.get("temperature"),
        "repeat": REPEAT,
        "accept": accept,
        "reject": reject,
        "counts": counts,
        "trials": trials,
    }
    path = Path(RESULTS_PATH)
    existing = {"runs": []}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing.setdefault("runs", [])
    existing["runs"].append(payload)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if accept == REPEAT else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        raise SystemExit(1)
    finally:
        stop_model(MODEL)
