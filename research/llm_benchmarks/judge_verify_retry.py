"""
Verifier 失敗後の Judge ベンチ。unittest ではない。

④の全工程は回さない。保存した失敗ケースだけを Judge に渡し、
JSON で missing を返して再調査に戻れるかを見る。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.judge_regression import JUDGE_CONTRACT_PHASE
from research.llm_benchmarks.judge_verify_retry_classify import inspect_judge_verify_retry
from tools.ai.llm.adapter import build_research_judge_messages, retry_extra
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.research_judge import create_research_judgment, normalize_judgment
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_JUDGE_RETRY_REPEAT") or 3)
CASE_ID = os.environ.get("AI_AGENT_JUDGE_RETRY_CASE") or "judge_verify_failed_retry"
RESULTS_PATH = "research/llm_benchmarks/judge_verify_retry_results.json"
BASELINE_PATH = "research/llm_benchmarks/judge_verify_retry_baseline_c.json"
REGRESSION_BASELINE_PATH = (
    "research/llm_benchmarks/judge_verify_retry_baseline_a.json"
)
CONTRACT_PHASE = JUDGE_CONTRACT_PHASE
PASS_CRITERION = "A"


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


def ask_json(materials, state):
    messages = build_research_judge_messages(materials, state=state)
    try:
        response = chat(model=MODEL, messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_research_judge_messages(
            materials, extra=retry_extra(), state=state
        )
        try:
            response = chat(model=MODEL, messages=messages)
            text = response.message.content
        except LLMTimeoutError as exc:
            return None, "timeout", str(exc)
        payload = extract_json_object(text)
    if payload is None:
        return None, "no_json", text
    return payload, None, text


def main():
    case = load_environment_case(CASE_ID)
    if not case:
        raise SystemExit(f"case がない: {CASE_ID}")
    state = TaskState.from_payload(case.get("state"))
    state = TaskState.from_payload(case.get("state"))
    materials = create_research_judgment(
        case["request"],
        case.get("proposal") or {"output": ["status"]},
        case.get("research_result") or {},
        state=state,
    )
    print(
        f"judge-verify-retry  case={CASE_ID}  repeat={REPEAT}  "
        f"profile={PROFILE_ID}  model={MODEL}"
    )
    trials = []
    try:
        for index in range(1, REPEAT + 1):
            with Timing() as clock:
                with stage("judge"):
                    payload, error, text = ask_json(materials, state)
            held = inspect_judge_verify_retry(payload, error)
            judgment = normalize_judgment(payload)
            mark = "PASS" if held["ok"] else held["grade"]
            print(
                f"{mark}  {index}/{REPEAT}  grade={held['grade']}  "
                f"retry={held['retry_ok']}  json={held['json_ok']}  "
                f"accept={judgment.get('satisfies_request')}  "
                f"missing={held['missing']}  "
                f"{(clock.snapshot() or {}).get('total_seconds')}s"
            )
            if held.get("reason"):
                print(f"  reason: {held['reason']}")
            if error:
                print(f"  error: {error}")
            trials.append(
                {
                    "n": index,
                    "ok": held["ok"],
                    "pass": held["ok"],
                    "held": held,
                    "error": error,
                    "answer": None if not isinstance(payload, dict) else payload,
                    "timing": clock.snapshot(),
                    "llm_text": text,
                }
            )
    finally:
        stop_model(MODEL)

    passed = all(item["ok"] for item in trials) and bool(trials)
    grades = {}
    for item in trials:
        grade = (item.get("held") or {}).get("grade") or "FAIL"
        grades[grade] = grades.get(grade, 0) + 1
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Verifier失敗後の missing の質。A/B/C/FAIL。④本体は回さない。正解コマンドは採点しない。",
        "contract_phase": CONTRACT_PHASE,
        "pass_criterion": PASS_CRITERION,
        "case": CASE_ID,
        "profile": PROFILE_ID,
        "model": MODEL,
        "repeat": REPEAT,
        "pass": passed,
        "ok": passed,
        "grades": grades,
        "trials": trials,
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
        f"pass={passed}  A={sum(1 for item in trials if item['ok'])}/{REPEAT}  "
        f"grades={grades}"
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
