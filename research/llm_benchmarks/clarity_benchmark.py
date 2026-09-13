"""
Clarity 専用ベンチ。unittest ではない。

3種の要求だけを渡し、status が期待どおりかを測る。
Research の findings は渡さない。プロンプトに混ざっていないことも機械確認する。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.clarity_classify import (
    classify_clarity_trial,
    inspect_project_context,
    inspect_research_isolation,
)
from tools.ai.llm.adapter import build_clarity_messages, retry_extra
from tools.ai.tool_builder.clarity import create_clarity_materials, normalize_clarity
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing
from tools.system.tool_builder.clarity import next_clarity_step


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_CLARITY_REPEAT") or 1)
CASE_ENV = os.environ.get("AI_AGENT_CLARITY_CASE", "").strip()
DEFAULT_CASES = (
    "clarity_memory_usage",
    "clarity_memory_ambiguous",
    "clarity_memory_vague",
)
RESULTS_PATH = "research/llm_benchmarks/clarity_results.json"


def selected_cases():
    if CASE_ENV:
        return [item.strip() for item in CASE_ENV.split(",") if item.strip()]
    return list(DEFAULT_CASES)


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


def ask_json(materials, profile):
    messages = build_clarity_messages(materials, profile=profile)
    isolation = inspect_research_isolation(messages, materials)
    context = inspect_project_context(messages)
    try:
        response = chat(model=profile["model"], messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc), messages, isolation, context
    payload = extract_json_object(text)
    if payload is None:
        messages = build_clarity_messages(
            materials, extra=retry_extra(profile), profile=profile
        )
        isolation = inspect_research_isolation(messages, materials)
        context = inspect_project_context(messages)
        try:
            response = chat(model=profile["model"], messages=messages)
            text = response.message.content
        except LLMTimeoutError as exc:
            return None, "timeout", str(exc), messages, isolation, context
        payload = extract_json_object(text)
    if payload is None:
        return None, "no_json", text, messages, isolation, context
    return payload, None, text, messages, isolation, context


def run_once(case, profile):
    request = case["request"]
    materials = create_clarity_materials(request)
    with Timing() as clock:
        payload, error, text, messages, isolation, context = ask_json(
            materials, profile
        )
        judgment = normalize_clarity(payload)
        labels = classify_clarity_trial(
            judgment,
            expect_status=case["expect_status"],
            isolation=isolation,
            text=text,
            expect_any=case.get("expect_any"),
            context=context,
        )
        if error:
            labels["ok"] = False
            labels["pass"] = False
            labels["error"] = error
    return {
        "ok": labels["ok"] and not error,
        "pass": labels["ok"] and not error,
        "error": error,
        "request": request,
        "expect_status": case["expect_status"],
        "expect_next_step": case.get("expect_next_step")
        or next_clarity_step({"status": case["expect_status"]}),
        "judgment": judgment,
        "labels": labels,
        "isolation": isolation,
        "context": context,
        "llm_text": text,
        "timing": clock.snapshot(),
        "material_keys": sorted(materials),
    }


def append_results(entry):
    path = Path(RESULTS_PATH)
    payload = {
        "note": "Clarity 3種。PROJECT_CONTEXT を渡し、Research は渡さない。質問内容も採点する。unittest ではない。",
        "runs": [],
    }
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("runs", [])
    payload["runs"].append(entry)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def print_trial(case_id, result, index, repeat):
    labels = result.get("labels") or {}
    mark = "PASS" if result.get("pass") else "FAIL"
    print(
        f"{mark}  {case_id}  {index}/{repeat}  "
        f"got={labels.get('status')}  expect={result.get('expect_status')}  "
        f"judge={labels.get('status_ok')}  "
        f"ask={labels.get('asked_only_when_needed')}  "
        f"user_q={labels.get('user_decision_question')}  "
        f"no_delegate={labels.get('did_not_delegate_method')}  "
        f"handoff={labels.get('handed_to_research')}  "
        f"isolated={labels.get('research_isolated')}  "
        f"{(result.get('timing') or {}).get('total_seconds')}s"
    )
    judgment = result.get("judgment") or {}
    if judgment.get("reason"):
        print(f"  reason: {judgment.get('reason')}")
    if judgment.get("question"):
        print(f"  question: {judgment.get('question')}")
    options = judgment.get("options") or []
    if options:
        labels_text = ", ".join(
            str(item.get("label") or item.get("id") or "") for item in options
        )
        print(f"  options: {labels_text}")
    if result.get("error"):
        print(f"  error: {result.get('error')}")
    leaks = (result.get("isolation") or {}).get("leaks") or []
    if leaks:
        print(f"  research_leak: {leaks}")
    if labels.get("resolved_without_asking"):
        print("  resolved_without_asking: true")
    if labels.get("invented_command"):
        print("  invented_command: true")
    if labels.get("delegated_method"):
        print("  delegated_method: true")
    if labels.get("expect_hit") is False:
        print("  expect_hit: false")


def main():
    case_ids = selected_cases()
    print(
        f"cases={case_ids}  repeat={REPEAT}  "
        f"profile={PROFILE_ID}  model={MODEL}"
    )
    passed = 0
    total = 0
    try:
        for case_id in case_ids:
            case = load_environment_case(case_id)
            if not case:
                raise SystemExit(f"case がない: {case_id}")
            for index in range(1, REPEAT + 1):
                result = run_once(case, PROFILE)
                total += 1
                if result["pass"]:
                    passed += 1
                print_trial(case_id, result, index, REPEAT)
                append_results(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "case": case_id,
                        "profile": PROFILE_ID,
                        "model": MODEL,
                        "n": index,
                        "ok": result["pass"],
                        "pass": result["pass"],
                        "error": result.get("error"),
                        "request": result.get("request"),
                        "expect_status": result.get("expect_status"),
                        "labels": result.get("labels"),
                        "judgment": {
                            "status": (result.get("judgment") or {}).get("status"),
                            "reason": (result.get("judgment") or {}).get("reason"),
                            "question": (result.get("judgment") or {}).get("question"),
                            "options": [
                                {
                                    "id": item.get("id"),
                                    "label": item.get("label"),
                                }
                                for item in (result.get("judgment") or {}).get("options")
                                or []
                            ],
                        },
                        "isolation": result.get("isolation"),
                        "context": result.get("context"),
                        "material_keys": result.get("material_keys"),
                        "timing": result.get("timing"),
                    }
                )
    finally:
        stop_model(MODEL)
    print(f"pass={passed}/{total}")
    return 0 if passed == total and total else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        raise SystemExit(1)
    finally:
        stop_model(MODEL)
