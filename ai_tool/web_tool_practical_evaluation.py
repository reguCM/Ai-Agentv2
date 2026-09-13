"""Web Tool Practical Evaluation Phase 1 — observation-only harness.

Does NOT modify production Agent, Registry, or tool implementations.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.agent_integration.gpu_process_e2e import build_production_agent_tools
from ai_tool.agent_integration.eval_production_parity_bridge import (
    eval_path_fields,
    diagnostic_path_fields,
    loop_to_trial_executions,
    run_canonical_web_eval,
)
from ai_tool.agent_integration.trial import (
    TrialExecutionRecord,
    TrialScenario,
    make_mock_chat_fn,
    run_trial_scenario,
)
from tools.system.network.search_web import search_web as real_search_web

RepoRoot = Path(__file__).resolve().parents[1]
Grade = Literal["PASS", "PARTIAL", "FAIL", "UNKNOWN"]
ProblemClass = Literal[
    "LLM_CAPABILITY",
    "PROMPT",
    "TOOL_SELECTION",
    "ARGUMENT_GENERATION",
    "AGENT_LOOP",
    "SEARCH_QUALITY",
    "FETCH_QUALITY",
    "SOURCE_EVALUATION",
    "RESULT_UTILIZATION",
    "SAFETY",
    "MODEL_CAPABILITY",
    "UNKNOWN",
]


@dataclass
class PracticalEvalCase:
    case_id: str
    label: str
    user_request: str
    focus: list[str]
    expectations: dict[str, Any] = field(default_factory=dict)
    deterministic_mock: TrialScenario | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.deterministic_mock:
            d["deterministic_mock"] = self.deterministic_mock.to_dict()
        return d


EVAL_CASES: list[PracticalEvalCase] = [
    PracticalEvalCase(
        case_id="A",
        label="単純検索",
        user_request="大阪市の人口について調べてください。",
        focus=["TOOL_SELECTION", "QUERY_GENERATION", "RESULT_UTILIZATION"],
        expectations={"min_search_web": 1, "min_read_url_text": 0},
        deterministic_mock=TrialScenario(
            scenario_id="practical_A",
            user_request="大阪市の人口について調べてください。",
            expected_tool="search_web",
            routing_note="simple search",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口", "limit": 5}},
            ],
            mock_final_answer="search_web の hits に基づき大阪市人口について報告（mock）。",
        ),
    ),
    PracticalEvalCase(
        case_id="B",
        label="Search → Fetch",
        user_request="大阪市の人口について検索して、見つかったページの内容を読んで説明してください。",
        focus=["DISCOVERY", "URL_SELECTION", "FETCH", "RESULT_UTILIZATION"],
        expectations={"min_search_web": 1, "min_read_url_text": 1, "requires_sequence": True},
        deterministic_mock=TrialScenario(
            scenario_id="practical_B",
            user_request="大阪市の人口について検索して、見つかったページの内容を読んで説明してください。",
            expected_tool="either",
            routing_note="search then fetch",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 公式", "limit": 3}},
                {"name": "read_url_text", "arguments": {"url": "https://example.com/osaka-population"}},
            ],
            mock_final_answer="検索後に read_url_text で取得した本文に基づく説明（mock）。",
        ),
    ),
    PracticalEvalCase(
        case_id="C",
        label="複数情報源比較",
        user_request="大阪市の人口について複数の情報源を調べ、それぞれの内容を比較して説明してください。",
        focus=["MULTI_SOURCE_RESEARCH", "SOURCE_DISTINCTION", "COMPARISON", "HALLUCINATION"],
        expectations={"min_search_web": 1, "min_total_tools": 2, "multi_source_signals": True},
        deterministic_mock=TrialScenario(
            scenario_id="practical_C",
            user_request="大阪市の人口について複数の情報源を調べ、それぞれの内容を比較して説明してください。",
            expected_tool="either",
            routing_note="multi source",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 統計", "limit": 5}},
                {"name": "read_url_text", "arguments": {"url": "https://example.com/source-a"}},
                {"name": "read_url_text", "arguments": {"url": "https://example.com/source-b"}},
            ],
            mock_final_answer="情報源AとBを比較（mock）。",
        ),
    ),
    PracticalEvalCase(
        case_id="D",
        label="最新情報",
        user_request="大阪市の現在の人口について最新情報を調べてください。",
        focus=["RECENCY_AWARENESS", "SOURCE_SELECTION", "UNCERTAINTY_HANDLING"],
        expectations={"min_search_web": 1, "recency_query_hint": True},
        deterministic_mock=TrialScenario(
            scenario_id="practical_D",
            user_request="大阪市の現在の人口について最新情報を調べてください。",
            expected_tool="search_web",
            routing_note="recency search",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 最新 2025", "limit": 5}},
            ],
            mock_final_answer="最新情報は search 結果から確認（mock）。日付不明は未確認とする。",
        ),
    ),
    PracticalEvalCase(
        case_id="E",
        label="情報不足・追加検索",
        user_request="1960年と2025年の大阪市人口の推移を調べ、両方の数値と変化の要点を説明してください。",
        focus=["INFORMATION_GAP_DETECTION", "ITERATIVE_SEARCH", "UNCERTAINTY_HANDLING"],
        expectations={"min_search_web": 2, "iterative_expected": True},
        deterministic_mock=TrialScenario(
            scenario_id="practical_E",
            user_request="1960年と2025年の大阪市人口の推移を調べ、両方の数値と変化の要点を説明してください。",
            expected_tool="either",
            routing_note="iterative search",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 1960", "limit": 5}},
                {"name": "search_web", "arguments": {"query": "大阪市 人口 2025", "limit": 5}},
            ],
            mock_final_answer="2回検索の結果を統合（mock）。不足は未確認。",
        ),
    ),
    PracticalEvalCase(
        case_id="F",
        label="情報源の品質差",
        user_request="大阪市の人口について、公式統計と一般的なWeb記事の両方を調べ、信頼性の違いに注意しながら説明してください。",
        focus=["SOURCE_EVALUATION", "PRIMARY_SOURCE_PREFERENCE", "CONFLICT_HANDLING"],
        expectations={"min_search_web": 1, "source_quality_signals": True},
        deterministic_mock=TrialScenario(
            scenario_id="practical_F",
            user_request="大阪市の人口について、公式統計と一般的なWeb記事の両方を調べ、信頼性の違いに注意しながら説明してください。",
            expected_tool="either",
            routing_note="source quality",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 公式 統計", "limit": 5}},
                {"name": "read_url_text", "arguments": {"url": "https://example.com/official-stats"}},
            ],
            mock_final_answer="公式と一般記事を区別して説明（mock）。",
        ),
    ),
    PracticalEvalCase(
        case_id="G",
        label="調査して要約",
        user_request="大阪市の人口について調べて、重要な点だけまとめてください。",
        focus=["END_TO_END_RESEARCH", "TOOL_SELECTION", "RESULT_UTILIZATION", "SUMMARY_QUALITY"],
        expectations={"min_search_web": 1},
        deterministic_mock=TrialScenario(
            scenario_id="practical_G",
            user_request="大阪市の人口について調べて、重要な点だけまとめてください。",
            expected_tool="search_web",
            routing_note="research summary",
            mock_tool_calls=[
                {"name": "search_web", "arguments": {"query": "大阪市 人口 概要", "limit": 5}},
                {"name": "read_url_text", "arguments": {"url": "https://example.com/osaka-summary"}},
            ],
            mock_final_answer="要点3つに要約（mock）。",
        ),
    ),
]


def production_web_eval_system_prompt(tool_names: list[str]) -> str:
    """Mirror agent.py web semantics without importing agent.py."""
    names = ", ".join(sorted(tool_names))
    return f"""
あなたはローカル環境のAI Agentです。評価実行中です。

利用可能 Tool: {names}

公開されている主なTool:
- search_web: Discovery — Web上の情報探索。queryで検索し title/snippet/URL 等のヒットを返す。URL本文取得は read_url_text。limitは返す件数。
- read_url_text: Fetch — 既知の HTTP/HTTPS URL の本文を read-only GET で取得する。URLが既に分かっているときのみ。探索には search_web。

Web調査の手順（Search → Fetch）:
1. URLが分からない・複数ソースを探す → search_web（Discovery）
2. 特定 URL の本文が必要 → read_url_text（Fetch）
3. 返ってきた hits / 本文をユーザー要求と照合し、関連性・十分性を確認する。
4. 無関係・不足なら query を組み直して再検索する。
5. 1件だけの無関係な結果を根拠に断定しない。
6. 回答で使うタイトル・URLは、実際に受け取った hits / fetch 結果に含まれるものだけを使う。
7. hits / 本文に無いURLや題名を補完しない。
8. 検索でも確認できない場合は「確認できなかった」と書く。

ルール:
- 必要な情報は公開Toolを呼び出して取得する。
- 存在しない引数名を捏造しない。各Toolの schema に従う。
- 不明なことは「未確認」と書く。
""".strip()


ChatFn = Callable[..., Any]


def _tool_names_from_executions(executions: list[TrialExecutionRecord | dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in executions:
        if isinstance(item, TrialExecutionRecord):
            names.append(item.selection.tool_name)
        else:
            sel = item.get("selection") or {}
            names.append(str(sel.get("tool_name") or ""))
    return [n for n in names if n]


def _extract_hit_tokens(executions: list[TrialExecutionRecord]) -> set[str]:
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
            content = str(result.get("content") or "")
            for word in re.findall(r"[0-9]{3,}|[一-龥ぁ-んァ-ン]{4,}", content):
                tokens.add(word)
            url = str(result.get("url") or "")
            if url:
                tokens.add(url)
    return tokens


def _mentions_tool_evidence(final_answer: str | None, tokens: set[str]) -> bool:
    if not final_answer or not tokens:
        return False
    answer = final_answer
    hits = 0
    for tok in tokens:
        if tok in answer or tok[:20] in answer:
            hits += 1
    return hits >= 1


def _grade_tool_selection(case: PracticalEvalCase, tool_names: list[str]) -> Grade:
    exp = case.expectations
    sw = tool_names.count("search_web")
    ru = tool_names.count("read_url_text")
    if not tool_names:
        return "FAIL"
    min_sw = int(exp.get("min_search_web") or 0)
    min_ru = int(exp.get("min_read_url_text") or 0)
    if sw < min_sw or ru < min_ru:
        return "FAIL"
    if exp.get("requires_sequence") and tool_names:
        saw_search = False
        saw_fetch_after = False
        for name in tool_names:
            if name == "search_web":
                saw_search = True
            elif name == "read_url_text" and saw_search:
                saw_fetch_after = True
        if not saw_fetch_after:
            return "PARTIAL"
    min_total = exp.get("min_total_tools")
    if min_total is not None and len(tool_names) < int(min_total):
        return "PARTIAL"
    if exp.get("iterative_expected") and sw < 2:
        return "PARTIAL"
    return "PASS"


def _grade_argument_generation(executions: list[TrialExecutionRecord]) -> Grade:
    if not executions:
        return "FAIL"
    partial = False
    for ex in executions:
        args = ex.selection.arguments
        if ex.selection.tool_name == "search_web":
            query = str(args.get("query") or "").strip()
            if not query:
                return "FAIL"
            if len(query) < 2:
                partial = True
        if ex.selection.tool_name == "read_url_text":
            url = str(args.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                return "FAIL"
            if ex.ok is False:
                partial = True
    return "PARTIAL" if partial else "PASS"


def _grade_result_utilization(
    case: PracticalEvalCase,
    executions: list[TrialExecutionRecord],
    final_answer: str | None,
) -> Grade:
    if not executions:
        return "FAIL"
    if not final_answer or len(final_answer.strip()) < 20:
        return "FAIL"
    tokens = _extract_hit_tokens(executions)
    if tokens and not _mentions_tool_evidence(final_answer, tokens):
        return "FAIL"
    if case.case_id == "C":
        if final_answer.count("情報源") + final_answer.count("ソース") + final_answer.count("比較") < 1:
            return "PARTIAL"
        if _tool_names_from_executions(executions).count("read_url_text") < 2 and len(executions) < 2:
            return "PARTIAL"
    if case.case_id == "D":
        if any(x in final_answer for x in ("最新", "現在", "2024", "2025")):
            pass
        else:
            return "PARTIAL"
        if "保証" in final_answer or "確実に最新" in final_answer:
            return "PARTIAL"
    return "PASS"


def _overall_case_grade(selection: Grade, args: Grade, util: Grade) -> Grade:
    grades = [selection, args, util]
    if "FAIL" in grades:
        if selection == "FAIL" or util == "FAIL":
            return "FAIL"
        return "PARTIAL"
    if "PARTIAL" in grades:
        return "PARTIAL"
    return "PASS"


def _detect_problems(
    case: PracticalEvalCase,
    tool_names: list[str],
    executions: list[TrialExecutionRecord],
    final_answer: str | None,
) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    sw = tool_names.count("search_web")
    ru = tool_names.count("read_url_text")

    if not tool_names:
        problems.append({"id": "4.1", "class": "TOOL_SELECTION", "note": "Web調査が必要だが Tool 未使用"})
    if case.expectations.get("min_read_url_text", 0) >= 1 and ru == 0 and sw >= 1:
        problems.append({"id": "4.3", "class": "RESULT_UTILIZATION", "note": "Search のみで Fetch なし"})
    if ru >= 1 and final_answer and not _mentions_tool_evidence(final_answer, _extract_hit_tokens(executions)):
        problems.append({"id": "4.4", "class": "RESULT_UTILIZATION", "note": "Fetch 実行後に本文が回答へ反映されない可能性"})
    if case.expectations.get("iterative_expected") and sw < 2:
        problems.append({"id": "4.5", "class": "AGENT_LOOP", "note": "情報不足なのに追加検索なし"})
    if len(tool_names) >= 5:
        problems.append({"id": "4.6", "class": "AGENT_LOOP", "note": "Tool 呼び出しが多い（上限付近）"})
    if case.case_id == "C" and sw >= 1 and ru == 0 and len(tool_names) == 1:
        problems.append({"id": "4.7", "class": "SOURCE_EVALUATION", "note": "複数情報源要求に単一 Search のみ"})
    return problems


def run_live_practical_case(
    case: PracticalEvalCase,
    *,
    chat_fn: ChatFn,
    model: str,
    max_rounds: int = 5,
    use_real_search: bool = True,
) -> dict[str, Any]:
    tools = build_production_agent_tools()
    tool_names_list = [t["function"]["name"] for t in tools]
    search_fn = real_search_web if use_real_search else None

    loop, meta = run_canonical_web_eval(
        case.user_request,
        chat_fn=chat_fn,
        model=model,
        search_web_fn=search_fn,
        max_rounds=max_rounds,
        live=use_real_search,
        scored=True,
        system_prompt=production_web_eval_system_prompt(tool_names_list),
    )
    executions = loop_to_trial_executions(loop)
    final_answer = loop.final_answer

    selected_tools = _tool_names_from_executions(executions)
    sel_grade = _grade_tool_selection(case, selected_tools)
    arg_grade = _grade_argument_generation(executions)
    util_grade = _grade_result_utilization(case, executions, final_answer)
    overall = _overall_case_grade(sel_grade, arg_grade, util_grade)
    problems = _detect_problems(case, selected_tools, executions, final_answer)

    return {
        "case_id": case.case_id,
        "label": case.label,
        "mode": "live_llm",
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
        "focus": case.focus,
        **eval_path_fields(meta),
    }


def run_deterministic_practical_case(case: PracticalEvalCase) -> dict[str, Any]:
    if case.deterministic_mock is None:
        return {"case_id": case.case_id, "mode": "deterministic", "overall": "UNKNOWN", "error": "no mock"}
    tools = build_production_agent_tools()
    result = run_trial_scenario(
        case.deterministic_mock,
        tools=tools,
        max_rounds=5,
    )
    executions_raw = result.executions
    # Re-wrap as TrialExecutionRecord-like for grading
    executions: list[TrialExecutionRecord] = list(executions_raw)
    selected_tools = _tool_names_from_executions(executions)
    sel_grade = _grade_tool_selection(case, selected_tools)
    arg_grade = _grade_argument_generation(executions)
    util_grade = _grade_result_utilization(case, executions, result.final_answer)
    overall = _overall_case_grade(sel_grade, arg_grade, util_grade)
    problems = _detect_problems(case, selected_tools, executions, result.final_answer)
    return {
        "case_id": case.case_id,
        "label": case.label,
        "mode": "deterministic_mock",
        "model": "mock",
        "user_request": case.user_request,
        "selected_tools": selected_tools,
        "tool_call_count": len(executions),
        "search_web_calls": selected_tools.count("search_web"),
        "read_url_text_calls": selected_tools.count("read_url_text"),
        "tool_arguments": [ex.selection.arguments for ex in executions],
        "tool_results": [ex.result for ex in executions],
        "executions": [ex.to_dict() for ex in executions],
        "final_answer": result.final_answer,
        "tool_selection": sel_grade,
        "argument_generation": arg_grade,
        "result_utilization": util_grade,
        "overall": overall,
        "problems": problems,
        "focus": case.focus,
        "note": "Deterministic mock — does NOT prove live LLM behavior; not production-equivalent",
        **diagnostic_path_fields(backend="trial_mock"),
        "path_label": "deterministic_mock",
    }


def aggregate_overall(case_results: list[dict[str, Any]], *, lane: str) -> Grade:
    if not case_results:
        return "UNKNOWN"
    grades = [str(r.get("overall") or "UNKNOWN") for r in case_results]
    if all(g == "PASS" for g in grades):
        return "PASS"
    if any(g == "FAIL" for g in grades):
        if sum(1 for g in grades if g == "FAIL") >= len(grades) // 2 + 1:
            return "FAIL"
        return "PARTIAL"
    if any(g == "PARTIAL" for g in grades):
        return "PARTIAL"
    return "UNKNOWN"


def classify_research_tool_necessity(all_problems: list[dict[str, Any]]) -> str:
    classes = {p.get("class") for p in all_problems}
    if "SOURCE_EVALUATION" in classes and len(all_problems) >= 3:
        return "CANDIDATE"
    return "NOT_ESTABLISHED"
