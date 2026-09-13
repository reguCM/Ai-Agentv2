"""
Context Persistence ベンチ。unittest ではない。

確定した意味を後半の質問へ持ち越せるかを測る。
推論力ではなく、エージェントの STATE 維持を見る。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.persistence_classify import all_recognized, classify_status_unit
from tools.ai.llm.adapter import (
    build_repair_messages,
    build_state_query_messages,
    retry_extra,
)
from tools.ai.state.task_state import TaskState
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
CASE_ID = os.environ.get("AI_AGENT_PERSIST_CASE") or "persist_status_unit_baseline"
REPEAT = int(os.environ.get("AI_AGENT_PERSIST_REPEAT") or 3)
MODES = [
    item.strip()
    for item in (
        os.environ.get("AI_AGENT_PERSIST_MODE") or "without_state"
    ).split(",")
    if item.strip()
]
GAPS_ENV = os.environ.get("AI_AGENT_PERSIST_GAPS", "").strip()
RESULTS_PATH = "research/llm_benchmarks/persistence_results.json"

REQUIRED_STATE_KEYS = ("status.meaning", "status.unit", "status.range")


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


def matches_expect(text, expect_any):
    haystack = str(text or "").lower()
    for token in expect_any or []:
        if str(token).lower() in haystack:
            return True
    return False


def ask_json(builder, materials, profile, *, state=None):
    messages = builder(materials, profile=profile, state=state)
    try:
        response = chat(model=profile["model"], messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = builder(
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


def haystack_from(kind, payload, text):
    parts = [text or ""]
    if not isinstance(payload, dict):
        return "\n".join(parts)
    if kind == "query":
        parts.append(str(payload.get("answer") or ""))
        parts.append(str(payload.get("reason") or ""))
        parts.extend(str(item) for item in payload.get("used_state_keys") or [])
    else:
        parts.append(str(payload.get("code") or ""))
        parts.append(str(payload.get("notes") or ""))
    return "\n".join(parts)


def run_round(round_spec, profile, *, state):
    kind = round_spec.get("kind") or "query"
    if kind == "repair":
        materials = dict(round_spec.get("materials") or {})
        if round_spec.get("question"):
            materials["question"] = round_spec["question"]
        builder = build_repair_messages
        stage_name = "repair"
    else:
        materials = dict(round_spec.get("materials") or {})
        materials["question"] = round_spec.get("question")
        builder = build_state_query_messages
        stage_name = "judge"
    with stage(stage_name):
        payload, error, text = ask_json(builder, materials, profile, state=state)
    haystack = haystack_from(kind, payload, text)
    labels = None
    classify = round_spec.get("classify")
    state_present = state is not None
    if classify in ("status_unit", "unit_ambiguous"):
        labels = classify_status_unit(haystack, state_present=state_present)
        if classify == "unit_ambiguous":
            passed = (not error) and bool(labels.get("unit_percent"))
        else:
            passed = (not error) and all_recognized(labels)
    else:
        expect = round_spec.get("expect_any")
        if expect:
            passed = (not error) and matches_expect(haystack, expect)
        else:
            passed = not error
    return {
        "id": round_spec.get("id"),
        "kind": kind,
        "question": round_spec.get("question"),
        "ok": passed,
        "error": error,
        "payload": payload,
        "llm_text": text,
        "labels": labels,
    }


def run_once(case, profile, *, with_state):
    state = None
    if with_state:
        state = TaskState.from_payload(case.get("state") or {"task": case.get("task")})
    with Timing() as clock:
        rounds = []
        for round_spec in case.get("rounds") or []:
            rounds.append(run_round(round_spec, profile, state=state))
        passed = all(item.get("ok") for item in rounds) if rounds else False
        return {
            "ok": passed,
            "pass": passed,
            "with_state": with_state,
            "rounds": rounds,
            "timing": clock.snapshot(),
        }


def inspect_state(state, *, with_state):
    if not with_state:
        return {"injected": False, "keys": [], "lost": False}
    if state is None:
        return {"injected": False, "keys": [], "lost": True}
    keys = [
        item.get("key")
        for item in (state.snapshot().get("decisions") or [])
        if item.get("key")
    ]
    lost = any(key not in keys for key in REQUIRED_STATE_KEYS)
    return {"injected": True, "keys": keys, "lost": lost}


def selected_gaps(case):
    if GAPS_ENV:
        return [int(item.strip()) for item in GAPS_ENV.split(",") if item.strip()]
    listed = case.get("gaps")
    if listed:
        return [int(item) for item in listed]
    return None


def run_gap_once(case, profile, *, with_state, gap):
    state = None
    if with_state:
        state = TaskState.from_payload(case.get("state") or {"task": case.get("task")})
    distractors = list(case.get("distractors") or [])
    if gap > len(distractors):
        raise ValueError(f"gap={gap} だが distractor は {len(distractors)} 件")
    final_spec = dict(case.get("final") or {})
    with Timing() as clock:
        prior_work = []
        inspections = []
        for item in distractors[:gap]:
            distractor = {
                "id": item.get("id"),
                "kind": "query",
                "question": item.get("question"),
                "materials": {"question": item.get("question")},
            }
            result = run_round(distractor, profile, state=state)
            answer = None
            if isinstance(result.get("payload"), dict):
                answer = result["payload"].get("answer")
            prior_work.append(
                {
                    "id": item.get("id"),
                    "question": item.get("question"),
                    "answer": answer,
                    "error": result.get("error"),
                }
            )
            inspections.append(inspect_state(state, with_state=with_state))
        materials = dict(final_spec.get("materials") or {})
        if prior_work:
            materials["prior_work"] = prior_work
        final_round = dict(final_spec)
        final_round["materials"] = materials
        last = run_round(final_round, profile, state=state)
        last["state"] = inspect_state(state, with_state=with_state)
        return {
            "ok": last.get("ok"),
            "pass": last.get("ok"),
            "with_state": with_state,
            "gap": gap,
            "state": last["state"],
            "inspections": inspections,
            "prior_work": prior_work,
            "rounds": [last],
            "timing": clock.snapshot(),
        }


def compact_round(item):
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    return {
        "id": item.get("id"),
        "kind": item.get("kind"),
        "ok": item.get("ok"),
        "error": item.get("error"),
        "answer": payload.get("answer"),
        "reason": payload.get("reason"),
        "labels": item.get("labels"),
    }


def append_results(entry):
    path = Path(RESULTS_PATH)
    payload = {"note": "STATE 維持ベンチ。unittest ではない。", "runs": []}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("runs", [])
    payload["runs"].append(entry)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def print_round(item):
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    labels = item.get("labels") or {}
    print(f"  answer: {(payload or {}).get('answer')}")
    print(f"  reason: {(payload or {}).get('reason')}")
    if labels:
        print(
            "  memory={recognized_memory_usage}  "
            "tool={recognized_tool_status}  "
            "unit={unit_percent}  "
            "generic={generic_status}  "
            "why={reason_class}".format(**labels)
        )


def print_gap_summary(rows):
    print("\n## gap summary")
    print("gap  mode           n  unit  why")
    for item in rows:
        labels = ((item.get("rounds") or [{}])[0].get("labels")) or {}
        lost = (item.get("state") or {}).get("lost")
        lost_mark = " STATE_LOST" if lost else ""
        print(
            f"{item.get('gap'):<4} {item.get('mode'):<14} "
            f"{item.get('n')}/{REPEAT}  "
            f"{labels.get('unit_percent')}  "
            f"{labels.get('reason_class')}{lost_mark}"
        )


def selected_models():
    listed = os.environ.get("AI_AGENT_PERSIST_MODELS", "").strip()
    if listed:
        return [item.strip() for item in listed.split(",") if item.strip()]
    if os.environ.get("AI_AGENT_MODEL"):
        return [os.environ["AI_AGENT_MODEL"].strip()]
    return [PROFILE_ID]


def main():
    case = load_environment_case(CASE_ID)
    if not case:
        raise SystemExit(f"case がない: {CASE_ID}")
    models = selected_models()
    gaps = selected_gaps(case)
    print(
        f"case={CASE_ID}  repeat={REPEAT}  modes={MODES}  "
        f"gaps={gaps or '-'}  models={models}"
    )
    summary_rows = []
    for profile_id in models:
        os.environ["AI_AGENT_MODEL"] = profile_id
        profile = get_llm_profile(profile_id)
        try:
            for mode in MODES:
                with_state = mode != "without_state"
                label = "with_state" if with_state else "without_state"
                gap_list = gaps if gaps is not None else [None]
                for gap in gap_list:
                    for index in range(1, REPEAT + 1):
                        if gap is None:
                            result = run_once(case, profile, with_state=with_state)
                        else:
                            result = run_gap_once(
                                case, profile, with_state=with_state, gap=gap
                            )
                        mark = "PASS" if result["pass"] else "FAIL"
                        gap_text = "" if gap is None else f"  gap={gap}"
                        lost = (result.get("state") or {}).get("lost")
                        lost_text = "  STATE_LOST" if lost else ""
                        print(
                            f"{mark}  {CASE_ID}  {profile_id} {label} "
                            f"{index}/{REPEAT}{gap_text}  "
                            f"{(result.get('timing') or {}).get('total_seconds')}s"
                            f"{lost_text}"
                        )
                        for item in result["rounds"]:
                            print_round(item)
                        row = {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "case": CASE_ID,
                            "profile": profile_id,
                            "model": profile["model"],
                            "n": index,
                            "mode": label,
                            "gap": result.get("gap") if gap is not None else None,
                            "ok": result["pass"],
                            "pass": result["pass"],
                            "state": result.get("state"),
                            "inspections": result.get("inspections"),
                            "prior_work": result.get("prior_work"),
                            "rounds": [compact_round(item) for item in result["rounds"]],
                            "timing": result.get("timing"),
                        }
                        append_results(row)
                        if gap is not None:
                            summary_rows.append(row)
        finally:
            stop_model(profile["model"])
    if summary_rows:
        print_gap_summary(summary_rows)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"NG  {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        raise SystemExit(1)
