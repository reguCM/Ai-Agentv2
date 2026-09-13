"""
Research 再調査の孤立ベンチ。unittest ではない。

④本体は回さない。固定材料で Web 候補生成だけを呼び、
失敗後に前回と異なる候補を出せるかを A/B/C/FAIL で見る。
"""

import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from research.llm_benchmarks.research_followup_classify import inspect_research_followup
from tools.ai.llm.adapter import (
    build_web_candidate_messages,
    exploration_retry_extra,
    retry_extra,
)
from tools.ai.tool_builder.research_judge import prepare_followup_research
from tools.ai.tool_builder.web import web_research
from tools.system.config import get_llm_profile
from tools.system.llm import LLMTimeoutError, chat, stop_model
from tools.system.llm_failure_memory import load_environment_case
from tools.system.timing import Timing, stage
from tools.system.tool_builder.research.web import (
    filter_relevant_hits,
    structure_search_keywords,
)


PROFILE = get_llm_profile()
MODEL = PROFILE["model"]
PROFILE_ID = PROFILE["id"]
REPEAT = int(os.environ.get("AI_AGENT_RESEARCH_FOLLOWUP_REPEAT") or 3)
CASE_ID = (
    os.environ.get("AI_AGENT_RESEARCH_FOLLOWUP_CASE")
    or "research_followup_after_verify_fail"
)
RESULTS_PATH = "research/llm_benchmarks/research_followup_results.json"
CONTRACT_PHASE = "research_followup_v3"
PASS_CRITERION = "A"
BASELINE_PATH = "research/llm_benchmarks/research_followup_baseline_c.json"
QUERY_SNAPSHOT_PATH = (
    "research/llm_benchmarks/research_followup_query_snapshot.json"
)


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


def build_research_from_case(case):
    prior = case.get("prior_round") or {}
    failed = prior.get("failed_command") or {}
    return {
        "usable_findings": [],
        "insufficient_findings": [],
        "unresolved": [
            {
                "kind": "output",
                "question": prior.get("judge_missing", ["output 'status' の取得方法"])[0],
                "finding": f"実環境で確認できなかった。{prior.get('error') or '失敗'}",
                "evidence": {
                    **failed,
                    "sample": [],
                    "error": prior.get("error"),
                },
                "confidence": "low",
                "source": "web",
            }
        ],
    }


def build_materials(case):
    prior = case.get("prior_round") or {}
    research = build_research_from_case(case)
    handoff = prepare_followup_research(
        prior.get("judge_missing") or [],
        research,
        reason=prior.get("judge_reason"),
    )
    subject = case.get("subject") or {}
    inventory = case.get("inventory") or {}
    keywords = []
    for question in handoff.get("followup_questions") or []:
        keywords.extend(
            structure_search_keywords(
                question, subject=subject, inventory=inventory
            )
        )
    # 同一固定ケースの search_results を使い、無関係ヒットだけ機械除外する
    filtered = filter_relevant_hits(
        case.get("search_results") or [],
        keywords=keywords,
        subject=subject,
    )
    return web_research(
        items=handoff["research_items"],
        search_results=filtered["hits"],
        inventory=inventory,
        subject=subject,
        environment={},
        rejected_commands=handoff["rejected_commands"],
        followup_questions=handoff["followup_questions"],
        prior_failures=handoff["prior_failures"],
        judge_reason=handoff["judge_reason"],
        search_keywords=keywords,
    ), {
        "keywords": keywords,
        "kept_count": filtered["kept_count"],
        "dropped_count": filtered["dropped_count"],
        "dropped_titles": [
            item.get("title") for item in filtered["dropped"][:5]
        ],
    }


def ask_json(materials, extra=None):
    messages = build_web_candidate_messages(materials, extra=extra)
    try:
        response = chat(model=MODEL, messages=messages)
        text = response.message.content
    except LLMTimeoutError as exc:
        return None, "timeout", str(exc)
    payload = extract_json_object(text)
    if payload is None:
        messages = build_web_candidate_messages(
            materials, extra=extra or retry_extra()
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


def ask_json_with_exploration_retry(materials, *, rejected, inventory, missing):
    payload, error, text = ask_json(materials)
    held = inspect_research_followup(
        payload,
        error,
        rejected_commands=rejected,
        inventory=inventory,
        missing=missing,
    )
    retried = False
    if (
        materials.get("empty_search")
        and held.get("grade") == "C"
        and not error
    ):
        payload, error, text = ask_json(
            materials, extra=exploration_retry_extra(materials)
        )
        held = inspect_research_followup(
            payload,
            error,
            rejected_commands=rejected,
            inventory=inventory,
            missing=missing,
        )
        retried = True
    return payload, error, text, held, retried


def main():
    case = load_environment_case(CASE_ID)
    if not case:
        raise SystemExit(f"case がない: {CASE_ID}")
    materials, filter_info = build_materials(case)
    prior = case.get("prior_round") or {}
    rejected = materials.get("rejected_commands") or []
    print(
        f"research-followup  case={CASE_ID}  repeat={REPEAT}  "
        f"profile={PROFILE_ID}  model={MODEL}  phase={CONTRACT_PHASE}"
    )
    print(f"  followup={materials.get('followup_questions')}")
    print(f"  rejected={len(rejected)}")
    print(
        "  filter: kept={kept} dropped={dropped} keywords={keywords}".format(
            kept=filter_info.get("kept_count"),
            dropped=filter_info.get("dropped_count"),
            keywords=filter_info.get("keywords"),
        )
    )
    if filter_info.get("dropped_titles"):
        print(f"  dropped_titles={filter_info.get('dropped_titles')}")
    if materials.get("empty_search"):
        hints = materials.get("exploration_hints") or []
        print(f"  empty_search=True  exploration_hints={len(hints)}")
    trials = []
    try:
        for index in range(1, REPEAT + 1):
            with Timing() as clock:
                with stage("research"):
                    payload, error, text, held, retried = ask_json_with_exploration_retry(
                        materials,
                        rejected=rejected,
                        inventory=materials.get("inventory") or {},
                        missing=prior.get("judge_missing"),
                    )
            mark = "PASS" if held["ok"] else held["grade"]
            print(
                f"{mark}  {index}/{REPEAT}  grade={held['grade']}  "
                f"candidates={held['candidate_count']}  "
                f"repeat={held['repeat_count']}  "
                f"substantive={held['substantive_count']}  "
                f"retried={retried}  "
                f"{(clock.snapshot() or {}).get('total_seconds')}s"
            )
            if error:
                print(f"  error: {error}")
            if isinstance(payload, dict):
                for idx, item in enumerate(payload.get("candidates") or [], start=1):
                    args = item.get("args") or []
                    preview = args[-1] if args else item.get("command")
                    print(f"  candidate[{idx}]: {str(preview)[:120]}")
            trials.append(
                {
                    "n": index,
                    "ok": held["ok"],
                    "pass": held["ok"],
                    "held": held,
                    "retried": retried,
                    "error": error,
                    "answer": payload,
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
        "note": "Judge missing 後の Research 再調査。同一固定 search_results + 機械フィルタ。④本体は回さない。",
        "contract_phase": CONTRACT_PHASE,
        "pass_criterion": PASS_CRITERION,
        "baseline": BASELINE_PATH,
        "query_snapshot": QUERY_SNAPSHOT_PATH,
        "case": CASE_ID,
        "profile": PROFILE_ID,
        "model": MODEL,
        "repeat": REPEAT,
        "filter": filter_info,
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
    print(f"pass={passed}  A={sum(1 for item in trials if item['ok'])}/{REPEAT}  grades={grades}")
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
