"""
複数候補から正しい取得方法を選べるかの孤立ベンチ。

5つの usable_findings を Judge に渡し、
要求(メモリ使用率)を満たす候補だけ ACCEPT するかを見る。
Research / Verifier は回さない。正解コマンドは契約に入れない。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.judge_select_method_classify import (
    inspect_judge_select_method,
)
from research.llm_benchmarks.judge_regression import JUDGE_CONTRACT_PHASE
from tools.ai.llm.adapter import build_research_judge_messages, retry_extra
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.research_judge import (
    create_research_judgment,
    normalize_judgment,
)
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_JUDGE_SELECT_REPEAT") or 3)
CASE_ID = (
    os.environ.get("AI_AGENT_JUDGE_SELECT_CASE")
    or "judge_select_method_memory_usage"
)
RESULTS_PATH = "research/llm_benchmarks/judge_select_method_results.json"
CONTRACT_PHASE = JUDGE_CONTRACT_PHASE
PASS_CRITERION = "CORRECT"


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
    materials = create_research_judgment(
        case["request"],
        case.get("proposal") or {"output": ["status"]},
        case.get("research_result") or {},
        state=state,
    )

    candidates = case.get("candidates") or {}
    accept_labels = sorted(
        label for label, meta in candidates.items() if meta.get("satisfies")
    )
    reject_labels = sorted(
        label for label, meta in candidates.items() if not meta.get("satisfies")
    )
    print(
        f"judge-select-method  case={CASE_ID}  repeat={REPEAT}  "
        f"profile={PROFILE_ID}  model={MODEL}"
    )
    print(f"  candidates={len(candidates)}  accept={accept_labels}  reject={reject_labels}")
    print(f"  usable_findings={len(materials.get('usable_findings') or [])}")

    trials = []
    try:
        for index in range(1, REPEAT + 1):
            with Timing() as clock:
                with stage("judge"):
                    payload, error, text = ask_json(materials, state)

            held = inspect_judge_select_method(payload, error, case=case)
            judgment = normalize_judgment(payload)
            mark = "PASS" if held["ok"] else held["grade"]

            print(
                f"{mark}  {index}/{REPEAT}  grade={held['grade']}  "
                f"accepted={held['accepted']}  "
                f"mentions={held['mentions']}  "
                f"{(clock.snapshot() or {}).get('total_seconds')}s"
            )
            if held.get("reason"):
                print(f"  reason: {held['reason']}")
            if held.get("missing"):
                print(f"  missing: {held['missing']}")
            if error:
                print(f"  error: {error}")

            trials.append(
                {
                    "n": index,
                    "ok": held["ok"],
                    "grade": held["grade"],
                    "accepted": held["accepted"],
                    "mentions": held["mentions"],
                    "accepted_labels": held["accepted_labels"],
                    "reason": held["reason"],
                    "missing": held["missing"],
                    "decisions": held["decisions"],
                    "error": error,
                    "seconds": (clock.snapshot() or {}).get("total_seconds"),
                }
            )
    except KeyboardInterrupt:
        print("中断")
    finally:
        stop_model()

    pass_count = sum(1 for trial in trials if trial["ok"])
    total = len(trials)
    summary = f"{PASS_CRITERION} {pass_count}/{total}"
    print(f"\n=== {summary} ===")

    result = {
        "case": CASE_ID,
        "contract_phase": CONTRACT_PHASE,
        "profile": PROFILE_ID,
        "model": MODEL,
        "repeat": REPEAT,
        "pass_count": pass_count,
        "total": total,
        "summary": summary,
        "trials": trials,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    Path(RESULTS_PATH).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved → {RESULTS_PATH}")


if __name__ == "__main__":
    main()
