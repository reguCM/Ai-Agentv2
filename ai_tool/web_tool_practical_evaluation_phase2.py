"""Web Tool Practical Evaluation Phase 2 — Evidence Pipeline re-run with minimal LLM prompt."""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from ai_tool.web_tool_practical_evaluation import (
    EVAL_CASES,
    PracticalEvalCase,
    _detect_problems,
    _grade_argument_generation,
    _grade_result_utilization,
    _grade_tool_selection,
    _overall_case_grade,
    _tool_names_from_executions,
    aggregate_overall,
)
from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
from ai_tool.agent_integration.eval_production_parity_bridge import (
    eval_path_fields,
    loop_to_trial_executions,
    run_canonical_web_eval,
)
from ai_tool.web_tool_practical_evaluation import (
    ChatFn,
    TrialExecutionRecord,
    _extract_hit_tokens,
    _mentions_tool_evidence,
)
from tools.system.network.search_web import search_web as real_search_web

RepoRoot = Path(__file__).resolve().parents[1]
BaselineRunDir = RepoRoot / "runs" / "ai_tool" / "20260828_201538_web_tool_practical_evaluation"
Layer = Literal["Tool", "Agent", "Prompt", "LLM", "Search", "Fetch", "MODEL_CAPABILITY", "UNKNOWN"]

HTML_META_MARKERS = ("HTML", "BeautifulSoup", "パーサー", "JSONデータ", "トリミング", "DOCTYPE")
HALLUCINATION_NUMERIC = re.compile(r"[0-9]{1,3}[,.]?[0-9]{3,}")


def minimal_web_eval_system_prompt(tool_names: list[str]) -> str:
    """Minimal prompt — no step-by-step Search/Fetch procedure."""
    names = ", ".join(sorted(tool_names))
    return f"""
あなたはローカル環境のAI Agentです。評価実行中です。

利用可能 Tool: {names}

ルール:
- 必要な情報は公開 Tool を使って取得する。
- 各 Tool の schema に従う。存在しない引数名を捏造しない。
- 不明なことは「未確認」と書く。
""".strip()


def _extract_hit_tokens_evidence(executions: list[TrialExecutionRecord]) -> set[str]:
    tokens: set[str] = set()
    for ex in executions:
        result = ex.result
        if not isinstance(result, dict):
            continue
        if ex.selection.tool_name == "search_web":
            for hit in result.get("hits") or []:
                if isinstance(hit, dict):
                    for key in ("title", "snippet", "url"):
                        val = str(hit.get(key) or "").strip()
                        if len(val) >= 4:
                            tokens.add(val[:80])
        if ex.selection.tool_name == "read_url_text":
            text = str(result.get("main_text") or result.get("content") or "")
            for word in re.findall(r"[0-9]{3,}|[一-龥ぁ-んァ-ン]{4,}", text):
                tokens.add(word)
            url = str(result.get("url") or "")
            if url:
                tokens.add(url)
    return tokens


def _has_html_meta_answer(final_answer: str | None) -> bool:
    if not final_answer:
        return False
    return any(m in final_answer for m in HTML_META_MARKERS)


def _has_hallucination_signal(
    final_answer: str | None,
    executions: list[TrialExecutionRecord],
) -> bool:
    if not final_answer:
        return False
    search_empty = any(
        isinstance(ex.result, dict)
        and ex.selection.tool_name == "search_web"
        and not (ex.result.get("hits") or [])
        for ex in executions
    )
    if not search_empty:
        return False
    return bool(HALLUCINATION_NUMERIC.search(final_answer))


def _fetch_fact_ready_any(executions: list[TrialExecutionRecord]) -> bool:
    for ex in executions:
        if ex.selection.tool_name != "read_url_text":
            continue
        result = ex.result if isinstance(ex.result, dict) else {}
        quality = result.get("quality") or {}
        if quality.get("fact_ready") is True:
            return True
    return False


def triage_case(
    case: PracticalEvalCase,
    executions: list[TrialExecutionRecord],
    final_answer: str | None,
    problems: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Map observed failures to responsibility layers."""
    findings: list[dict[str, str]] = []
    tool_names = _tool_names_from_executions(executions)

    if _has_html_meta_answer(final_answer):
        if _fetch_fact_ready_any(executions):
            findings.append({"layer": "LLM", "note": "fact_ready evidence exists but answer is HTML/JSON meta"})
        else:
            findings.append({"layer": "Fetch", "note": "fetch returned non-fact-ready main_text; LLM fell back to meta analysis"})
            findings.append({"layer": "LLM", "note": "responded with HTML structure instead of user question"})

    if _has_hallucination_signal(final_answer, executions):
        findings.append({"layer": "LLM", "note": "numeric claim after empty search"})
        findings.append({"layer": "Agent", "note": "grounding invariant may not have prevented hallucination in eval harness"})

    for ex in executions:
        if ex.selection.tool_name != "search_web" or not isinstance(ex.result, dict):
            continue
        hits = ex.result.get("hits") or []
        if not hits:
            findings.append({"layer": "Search", "note": f"empty hits for query={ex.selection.arguments.get('query')!r}"})
        for hit in hits:
            if isinstance(hit, dict) and hit.get("relevance_hint") == "low":
                findings.append({"layer": "Search", "note": f"low relevance hit: {hit.get('title')}"})

    if case.expectations.get("min_read_url_text", 0) >= 1 and tool_names.count("read_url_text") == 0:
        findings.append({"layer": "LLM", "note": "did not call read_url_text when user requested reading page"})
        findings.append({"layer": "Agent", "note": "no enforced fetch-after-search in eval harness (prompt-only)"})

    if tool_names.count("read_url_text") >= 1 and final_answer:
        tokens = _extract_hit_tokens_evidence(executions)
        if tokens and not _mentions_tool_evidence(final_answer, tokens):
            if _fetch_fact_ready_any(executions):
                findings.append({"layer": "LLM", "note": "did not use main_text evidence in final answer"})
            else:
                findings.append({"layer": "Fetch", "note": "main_text not fact-ready; LLM could not ground answer"})

    if len(tool_names) >= 5 and not final_answer:
        findings.append({"layer": "Agent", "note": "max tool rounds exhausted without final answer"})
        findings.append({"layer": "LLM", "note": "continued search without fetch/synthesis"})

    if not findings and problems:
        for p in problems:
            cls = p.get("class", "UNKNOWN")
            layer = "LLM"
            if cls in ("SEARCH_QUALITY",):
                layer = "Search"
            elif cls in ("FETCH_QUALITY",):
                layer = "Fetch"
            elif cls in ("AGENT_LOOP",):
                layer = "Agent"
            findings.append({"layer": layer, "note": p.get("note", "")})

    if not findings and not problems:
        findings.append({"layer": "UNKNOWN", "note": "no problems detected by harness"})

    # dedupe
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for f in findings:
        key = (f["layer"], f["note"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def run_live_practical_case_phase2(
    case: PracticalEvalCase,
    *,
    chat_fn: ChatFn,
    model: str,
    max_rounds: int = 5,
) -> dict[str, Any]:
    tools = build_production_agent_tools()
    tool_names_list = [t["function"]["name"] for t in tools]

    loop, meta = run_canonical_web_eval(
        case.user_request,
        chat_fn=chat_fn,
        model=model,
        search_web_fn=real_search_web,
        max_rounds=max_rounds,
        live=True,
        scored=True,
        system_prompt=minimal_web_eval_system_prompt(tool_names_list),
    )
    executions = loop_to_trial_executions(loop)
    final_answer = loop.final_answer

    selected_tools = _tool_names_from_executions(executions)
    sel_grade = _grade_tool_selection(case, selected_tools)
    arg_grade = _grade_argument_generation(executions)
    util_grade = _grade_result_utilization(case, executions, final_answer)
    overall = _overall_case_grade(sel_grade, arg_grade, util_grade)
    problems = _detect_problems(case, selected_tools, executions, final_answer)
    triage = triage_case(case, executions, final_answer, problems)

    evidence_summary = {
        "any_fact_ready": _fetch_fact_ready_any(executions),
        "html_meta_answer": _has_html_meta_answer(final_answer),
        "hallucination_signal": _has_hallucination_signal(final_answer, executions),
        "empty_search_calls": sum(
            1
            for ex in executions
            if ex.selection.tool_name == "search_web"
            and isinstance(ex.result, dict)
            and not (ex.result.get("hits") or [])
        ),
    }

    return {
        "case_id": case.case_id,
        "label": case.label,
        "mode": "live_llm_phase2_minimal_prompt",
        "model": model,
        "user_request": case.user_request,
        "selected_tools": selected_tools,
        "tool_call_count": len(executions),
        "search_web_calls": selected_tools.count("search_web"),
        "read_url_text_calls": selected_tools.count("read_url_text"),
        "tool_arguments": [ex.selection.arguments for ex in executions],
        "tool_results": [ex.result for ex in executions],
        "executions": [ex.to_dict() for ex in executions],
        "final_answer": final_answer,
        "raw_llm_answer": loop.raw_llm_answer,
        "web_status_overall": (loop.web_session_aggregate or {}).get("overall"),
        "tool_selection": sel_grade,
        "argument_generation": arg_grade,
        "result_utilization": util_grade,
        "overall": overall,
        "problems": problems,
        "triage": triage,
        "evidence_summary": evidence_summary,
        "focus": case.focus,
        "prompt_variant": "minimal",
        **eval_path_fields(meta),
    }


def load_baseline_case(case_id: str) -> dict[str, Any] | None:
    path = BaselineRunDir / f"case_{case_id}_live_supplementary.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_with_baseline(phase2: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if baseline is None:
        return {"baseline_missing": True}
    return {
        "baseline_overall": baseline.get("overall"),
        "phase2_overall": phase2.get("overall"),
        "delta_overall": _delta_grade(baseline.get("overall"), phase2.get("overall")),
        "baseline_tools": baseline.get("selected_tools"),
        "phase2_tools": phase2.get("selected_tools"),
        "baseline_utilization": baseline.get("result_utilization"),
        "phase2_utilization": phase2.get("result_utilization"),
        "baseline_html_meta": _has_html_meta_answer(baseline.get("final_answer")),
        "phase2_html_meta": phase2.get("evidence_summary", {}).get("html_meta_answer"),
        "phase2_fact_ready": phase2.get("evidence_summary", {}).get("any_fact_ready"),
    }


def _delta_grade(before: Any, after: Any) -> str:
    order = {"FAIL": 0, "PARTIAL": 1, "PASS": 2, "UNKNOWN": -1}
    b = order.get(str(before), -1)
    a = order.get(str(after), -1)
    if a > b:
        return "IMPROVED"
    if a < b:
        return "REGRESSED"
    return "UNCHANGED"


def summarize_triage(all_cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in all_cases:
        for item in case.get("triage") or []:
            layer = str(item.get("layer") or "UNKNOWN")
            counts[layer] = counts.get(layer, 0) + 1
    return counts
