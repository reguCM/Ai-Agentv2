"""
Proposal 生成の孤立ベンチ。unittest ではない。

STATE を固定し、LLM に proposal を生成させて
module/function/category 等が Implementation に渡せる品質かを検査する。
Research/Judge/Implementation は回さない。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.proposal_classify import inspect_proposal
from tools.ai.llm.adapter import build_proposal_messages, retry_extra, validation_extra
from tools.ai.state.task_state import TaskState
from tools.ai.tool_builder.proposal import PROJECT_CONVENTIONS, create_tool_proposal
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage
from tools.system.tool_builder.validate.proposal_completeness import (
    validate_proposal_completeness,
)
from tools.system.tool_builder.validate.spec import validate_tool_spec


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_PROPOSAL_REPEAT") or 3)
CASE_ID = os.environ.get("AI_AGENT_PROPOSAL_CASE") or "proposal_memory_usage"
RESULTS_PATH = "research/llm_benchmarks/proposal_results.json"


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
    messages = build_proposal_messages(materials, state=state)
    try:
        response = chat(model=MODEL, messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_proposal_messages(
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


def ask_json_with_hint(materials, state, hint):
    messages = build_proposal_messages(
        materials, extra=hint, state=state
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

    materials = create_tool_proposal(
        case["request"],
        project_spec=PROJECT_CONVENTIONS,
        registry=[],
        environment=None,
    )
    materials["structure_hint"] = {
        "module_pattern": "tools.<category>.<subcategory>.<filename>",
        "return_shape": {"status": "値"},
        "note": "参考は配置と戻り値の形だけ。取得コマンドはここにない。",
    }

    print(
        f"proposal-benchmark  case={CASE_ID}  repeat={REPEAT}  "
        f"profile={PROFILE_ID}  model={MODEL}"
    )

    trials = []
    try:
        for index in range(1, REPEAT + 1):
            retried = False
            with Timing() as clock:
                with stage("proposal"):
                    payload, error, text = ask_json(materials, state)

                if not error and isinstance(payload, dict):
                    proposals = payload.get("proposals") or []
                    if proposals:
                        check = validate_proposal_completeness(proposals[0])
                        if not check["ok"]:
                            payload, error, text = ask_json_with_hint(
                                materials, state, check["hint"]
                            )
                            retried = True

            held = inspect_proposal(payload, error, case=case)
            held["retried"] = retried
            mark = "PASS" if held["ok"] else held["grade"]

            retry_tag = "  retried" if retried else ""
            print(
                f"{mark}  {index}/{REPEAT}  grade={held['grade']}  "
                f"name={held['proposal_name']}  "
                f"module={held['module']}  "
                f"function={held['function']}  "
                f"category={held['category']}  "
                f"{(clock.snapshot() or {}).get('total_seconds')}s{retry_tag}"
            )
            if held.get("missing_keys"):
                print(f"  missing_keys: {held['missing_keys']}")
            if not all(held.get("checks", {}).values()):
                failed_checks = {
                    k: v for k, v in held.get("checks", {}).items() if not v
                }
                print(f"  failed_checks: {failed_checks}")
            if error:
                print(f"  error: {error}")

            trials.append(
                {
                    "n": index,
                    "ok": held["ok"],
                    "grade": held["grade"],
                    "proposal_name": held["proposal_name"],
                    "module": held["module"],
                    "function": held["function"],
                    "category": held["category"],
                    "subcategory": held["subcategory"],
                    "output": held["output"],
                    "checks": held["checks"],
                    "missing_keys": held["missing_keys"],
                    "error": error,
                    "seconds": (clock.snapshot() or {}).get("total_seconds"),
                }
            )
    except KeyboardInterrupt:
        print("中断")
    finally:
        stop_model()

    pass_count = sum(1 for t in trials if t["ok"])
    total = len(trials)
    summary = f"COMPLETE {pass_count}/{total}"
    print(f"\n=== {summary} ===")

    result = {
        "case": CASE_ID,
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
