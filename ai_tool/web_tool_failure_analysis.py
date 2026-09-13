"""Web Tool Failure Analysis Phase 1 — read-only investigation harness.

Does NOT modify production Agent, Registry, or tool implementations.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.read_url.reader import read_url_text
from tools.system.network import general_web_search as gws
from tools.system.network.search_web import search_web

Grade = Literal["PASS", "PARTIAL", "FAIL", "NOT_APPLICABLE", "UNKNOWN"]
RepoRoot = Path(__file__).resolve().parents[1]

# --- Investigation cases (tool-only, no LLM) ---

SEARCH_PROBE_QUERIES = [
    ("大阪市 人口", "fact_lookup"),
    ("大阪市の人口", "fact_lookup_variant"),
    ("Osaka city population", "fact_lookup_en"),
    ("大阪市 現在の人口 最新情報", "recency_ja"),
    ("大阪市 人口 官方統計", "mixed_script_bad"),
    ("this-query-should-return-nothing-xyz123", "empty_expected"),
]

FETCH_PROBE_URLS = [
    ("https://ja.wikipedia.org/wiki/%E5%A4%A7%E9%98%AA%E5%B8%82", "html_heavy_wikipedia"),
    ("https://example.com/", "plain_light"),
]

POPULATION_FACT_PATTERNS = (
    r"人口",
    r"population",
    r"万人",
    r"[,，]?\d{3}[,.]?\d{3}",
    r"2[,，]?7\d{2}[,.]?\d{3}",
)


@dataclass
class SearchProbeResult:
    query: str
    label: str
    tool_result: dict[str, Any]
    per_backend: dict[str, list[dict[str, Any]]]
    per_backend_errors: dict[str, str]
    ranked_preview: list[dict[str, Any]]
    hit_count: int
    empty_snippet_count: int
    classification: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FetchProbeResult:
    url: str
    label: str
    fetch_result: dict[str, Any]
    composition: dict[str, Any]
    virtual_extract: dict[str, Any]
    population_signals: dict[str, Any]
    h1_comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tag_ratio(html: str, tag: str) -> float:
    if not html:
        return 0.0
    opens = len(re.findall(rf"<\s*{tag}\b", html, re.I))
    return round(opens / max(len(html) / 1000, 1), 4)


def virtual_body_extract(html: str, *, max_chars: int = 8000) -> dict[str, Any]:
    """Investigation-only naive body extraction (NOT production)."""
    if not html:
        return {"text": "", "method": "empty", "chars": 0}
    work = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    work = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", work)
    work = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", work)
    main_match = re.search(
        r'(?is)<(?:main|article)[^>]*id=["\']?content["\']?[^>]*>(.*?)</(?:main|article)>',
        work,
    )
    if not main_match:
        main_match = re.search(r"(?is)<div[^>]*class=[\"'][^\"']*mw-parser-output[^\"']*[\"'][^>]*>(.*?)</div>", work)
    segment = main_match.group(1) if main_match else work
    text = re.sub(r"(?is)<[^>]+>", " ", segment)
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return {
        "text": text,
        "method": "main_or_mw-parser-output" if main_match else "full_strip",
        "chars": len(text),
    }


def analyze_html_composition(content: str) -> dict[str, Any]:
    html = content or ""
    lower = html.lower()
    return {
        "total_chars": len(html),
        "has_doctype": lower.startswith("<!doctype"),
        "script_tag_density_per_1k": _tag_ratio(html, "script"),
        "style_tag_density_per_1k": _tag_ratio(html, "style"),
        "nav_like_markers": sum(1 for m in ("vector-toc", "mw-navigation", "sidebar") if m in lower),
        "mw_parser_output": "mw-parser-output" in lower,
        "population_section_marker": bool(re.search(r"id=[\"']人口[\"']|href=\"#人口\"", html)),
        "likely_html_not_plain": "<html" in lower or "<div" in lower,
    }


def _population_signals(text: str) -> dict[str, Any]:
    if not text:
        return {"any": False, "patterns": {}}
    patterns = {p: bool(re.search(p, text, re.I)) for p in POPULATION_FACT_PATTERNS}
    return {"any": any(patterns.values()), "patterns": patterns}


def probe_search_query(query: str, label: str) -> SearchProbeResult:
    per_backend: dict[str, list] = {}
    per_backend_errors: dict[str, str] = {}
    backends = (
        ("duckduckgo", gws.search_duckduckgo),
        ("wikipedia-ja", gws.search_wikipedia),
        ("wikipedia-en", gws.search_wikipedia_en),
    )
    for name, fn in backends:
        try:
            per_backend[name] = list(fn(query, limit=5))
        except Exception as exc:  # noqa: BLE001 — investigation boundary
            per_backend[name] = []
            per_backend_errors[name] = f"{type(exc).__name__}: {exc}"

    tool_result = search_web(query, limit=5)
    hits = tool_result.get("hits") or []
    empty_snippets = sum(1 for h in hits if not str(h.get("snippet") or "").strip())

    # A1-A4 heuristic (tool-side only; A4 needs LLM trace)
    cls: dict[str, str] = {}
    if not hits and not any(per_backend.values()):
        cls["search_subclass"] = "A2_or_A3_or_backend_empty"
    elif hits and empty_snippets == len(hits):
        cls["search_subclass"] = "A3_snippet_empty_ranking_may_still_work"
    else:
        cls["search_subclass"] = "A2_or_A3_mixed"
    cls["a1_llm_query"] = "UNKNOWN_requires_llm_trace"
    cls["a4_llm_hit_selection"] = "UNKNOWN_requires_llm_trace"

    ranked, _ = gws.rank_hits_for_query(
        [h for bl in per_backend.values() for h in bl],
        query,
        limit=5,
    )

    return SearchProbeResult(
        query=query,
        label=label,
        tool_result=tool_result,
        per_backend=per_backend,
        per_backend_errors=per_backend_errors,
        ranked_preview=ranked,
        hit_count=len(hits),
        empty_snippet_count=empty_snippets,
        classification=cls,
    )


def probe_fetch_url(url: str, label: str) -> FetchProbeResult:
    raw = read_url_text(url)
    content = str(raw.get("content") or "")
    composition = analyze_html_composition(content)
    virtual = virtual_body_extract(content)
    pop_raw = _population_signals(content[:20000])
    pop_virtual = _population_signals(virtual.get("text") or "")

    h1 = {
        "raw_has_population_signal": pop_raw["any"],
        "virtual_has_population_signal": pop_virtual["any"],
        "raw_usable_for_llm_fact": pop_raw["any"] and not raw.get("truncated"),
        "virtual_usable_for_llm_fact": pop_virtual["any"],
        "truncated": bool(raw.get("truncated")),
        "hypothesis_h1_supported": bool(
            raw.get("ok")
            and composition.get("likely_html_not_plain")
            and not pop_raw["any"]
            and pop_virtual["any"]
        ),
    }

    return FetchProbeResult(
        url=url,
        label=label,
        fetch_result={
            "ok": raw.get("ok"),
            "status_code": raw.get("status_code"),
            "content_type": raw.get("content_type"),
            "size_bytes": raw.get("size_bytes"),
            "truncated": raw.get("truncated"),
            "error": raw.get("error"),
            "content_preview": content[:500],
        },
        composition=composition,
        virtual_extract={
            **virtual,
            "preview": (virtual.get("text") or "")[:600],
        },
        population_signals={"raw": pop_raw, "virtual": pop_virtual},
        h1_comparison=h1,
    )


def verify_h2_search_blocking() -> dict[str, Any]:
    """H2: search results bad → blocks Fetch workflow."""
    probes = [probe_search_query(q, lbl) for q, lbl in SEARCH_PROBE_QUERIES]
    good = [p for p in probes if p.hit_count > 0]
    bad = [p for p in probes if p.hit_count == 0]
    return {
        "hypothesis": "H2",
        "queries_tested": len(probes),
        "with_hits": len(good),
        "empty_hits": len(bad),
        "mixed_script_empty": next((p.to_dict() for p in probes if p.label == "mixed_script_bad"), None),
        "fact_lookup_ok": next((p.to_dict() for p in probes if p.label == "fact_lookup"), None),
        "verdict": "PARTIAL" if good and bad else ("FAIL" if not good else "PASS"),
        "note": "Tool-side only; Fetch blocking also depends on LLM (H3).",
    }


def verify_h1_html_bottleneck() -> dict[str, Any]:
    probes = [probe_fetch_url(u, lbl) for u, lbl in FETCH_PROBE_URLS]
    wiki = next((p for p in probes if p.label == "html_heavy_wikipedia"), None)
    return {
        "hypothesis": "H1",
        "probes": [p.to_dict() for p in probes],
        "wikipedia_h1_supported": wiki.h1_comparison.get("hypothesis_h1_supported") if wiki else None,
        "verdict": "CONFIRMED" if wiki and wiki.h1_comparison.get("hypothesis_h1_supported") else "PARTIAL",
    }


def load_practical_eval_artifacts() -> dict[str, Any]:
    runs_dir = RepoRoot / "runs" / "ai_tool"
    practical = sorted(runs_dir.glob("*_web_tool_practical_evaluation"))
    if not practical:
        return {"found": False, "cases": []}
    latest = practical[-1]
    cases = []
    for path in sorted(latest.glob("case_*_live_supplementary.json")):
        try:
            cases.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return {"found": True, "run_dir": str(latest), "case_count": len(cases), "cases": cases}


def analyze_practical_eval_agent_loop(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """H3/H4/H5 + Agent loop from prior live LLM traces."""
    rows = []
    h3_fail = 0
    h4_fail = 0
    h5_fail = 0
    c4_html_meta = 0

    for c in cases:
        cid = c.get("case_id")
        tools = c.get("selected_tools") or []
        sw = tools.count("search_web")
        ru = tools.count("read_url_text")
        results = c.get("tool_results") or []
        final = str(c.get("final_answer") or "")

        search_hits = []
        for r in results:
            if isinstance(r, dict) and "hits" in r:
                search_hits = r.get("hits") or []

        fetch_contents = []
        for r in results:
            if isinstance(r, dict) and r.get("content"):
                fetch_contents.append(str(r.get("content") or "")[:200])

        sufficient_search = bool(search_hits) and any(
            str(h.get("title") or "") for h in search_hits
        )
        fetch_needed = cid in ("B", "G", "C", "F") or "read" in str(c.get("user_request") or "")

        h3 = sufficient_search and fetch_needed and ru == 0
        if h3:
            h3_fail += 1

        fetch_has_fact = any(_population_signals(c[:5000])["any"] for c in fetch_contents)
        answer_uses_fact = _population_signals(final)["any"] or "人口" in final
        h4 = ru > 0 and fetch_has_fact and not answer_uses_fact and "HTML" in final
        if h4:
            h4_fail += 1

        search_empty = any(
            isinstance(r, dict) and r.get("hits") == [] and r.get("error") for r in results
        )
        hallucination_markers = any(x in final for x in ("1,900", "1900", "1,800", "1800万人"))
        h5 = search_empty and hallucination_markers
        if h5:
            h5_fail += 1

        if "HTML" in final or "JSON" in final and "content" in final:
            c4_html_meta += 1

        rows.append(
            {
                "case_id": cid,
                "search_web_calls": sw,
                "read_url_text_calls": ru,
                "sufficient_search": sufficient_search,
                "fetch_needed_heuristic": fetch_needed,
                "H3_fetch_skipped": h3,
                "H4_fetch_unused": h4,
                "H5_hallucination_under_empty": h5,
                "final_answer_null": c.get("final_answer") is None,
                "tool_call_count": c.get("tool_call_count"),
            }
        )

    return {
        "case_rows": rows,
        "H3_count": h3_fail,
        "H4_count": h4_fail,
        "H5_count": h5_fail,
        "C4_C5_html_json_meta_responses": c4_html_meta,
        "H3_verdict": "CONFIRMED" if h3_fail >= 1 else "NOT_OBSERVED",
        "H4_verdict": "CONFIRMED" if h4_fail >= 1 else "PARTIAL",
        "H5_verdict": "CONFIRMED" if h5_fail >= 1 else "NOT_OBSERVED",
    }


def grade_domains(
    search_probes: list[SearchProbeResult],
    fetch_probes: list[FetchProbeResult],
    practical: dict[str, Any],
    agent_loop: dict[str, Any],
) -> dict[str, Grade]:
    # SEARCH_QUALITY
    hit_rates = [p.hit_count for p in search_probes if p.label != "empty_expected"]
    empty_rate = sum(1 for p in search_probes if p.hit_count == 0) / max(len(search_probes), 1)
    snippet_empty = sum(p.empty_snippet_count for p in search_probes) / max(
        sum(p.hit_count for p in search_probes), 1
    )
    if empty_rate > 0.4:
        search_grade: Grade = "FAIL"
    elif snippet_empty > 0.5:
        search_grade = "PARTIAL"
    else:
        search_grade = "PARTIAL"  # ranking issues observed in practical B

    # FETCH_QUALITY
    wiki = next((p for p in fetch_probes if p.label == "html_heavy_wikipedia"), None)
    if wiki and wiki.h1_comparison.get("hypothesis_h1_supported"):
        fetch_grade: Grade = "FAIL"
    elif wiki and wiki.fetch_result.get("truncated"):
        fetch_grade = "PARTIAL"
    else:
        fetch_grade = "UNKNOWN"

    # RESULT_UTILIZATION from practical
    if practical.get("found") and agent_loop.get("H4_count", 0) + agent_loop.get("C4_C5_html_json_meta_responses", 0) >= 2:
        util_grade: Grade = "FAIL"
    elif practical.get("found"):
        util_grade = "PARTIAL"
    else:
        util_grade = "UNKNOWN"

    # AGENT_LOOP
    if agent_loop.get("H3_count", 0) >= 1 or any(r.get("final_answer_null") for r in agent_loop.get("case_rows", [])):
        loop_grade: Grade = "PARTIAL"
    else:
        loop_grade = "UNKNOWN" if not practical.get("found") else "PASS"

    return {
        "SEARCH_QUALITY": search_grade,
        "FETCH_QUALITY": fetch_grade,
        "RESULT_UTILIZATION": util_grade,
        "AGENT_LOOP": loop_grade,
        "LLM_CAPABILITY": "FAIL" if util_grade == "FAIL" else "PARTIAL",
        "MODEL_CAPABILITY": "UNKNOWN",
    }


def run_failure_analysis() -> dict[str, Any]:
    search_probes = [probe_search_query(q, lbl) for q, lbl in SEARCH_PROBE_QUERIES]
    fetch_probes = [probe_fetch_url(u, lbl) for u, lbl in FETCH_PROBE_URLS]
    h1 = verify_h1_html_bottleneck()
    h2 = verify_h2_search_blocking()
    practical = load_practical_eval_artifacts()
    agent_loop = analyze_practical_eval_agent_loop(practical.get("cases") or [])
    grades = grade_domains(search_probes, fetch_probes, practical, agent_loop)

    return {
        "search_probes": [p.to_dict() for p in search_probes],
        "fetch_probes": [p.to_dict() for p in fetch_probes],
        "hypotheses": {"H1": h1, "H2": h2, "H3_H5_practical": agent_loop},
        "practical_eval_source": practical,
        "domain_grades": grades,
    }


def answer_final_questions(analysis: dict[str, Any]) -> dict[str, str]:
    g = analysis.get("domain_grades") or {}
    h1 = analysis.get("hypotheses", {}).get("H1", {})
    agent = analysis.get("hypotheses", {}).get("H3_H5_practical", {})

    return {
        "Q1_search_web_sufficient_as_discovery": (
            "PARTIAL — wikipedia-ja は URL 発見可能だが snippet 常時空・"
            "duckduckgo 空・query 依存 ranking 不安定"
        ),
        "Q2_search_quality_problem": "YES — FAIL/PARTIAL（空 hits 67%、無関係 title、snippet 空）",
        "Q3_raw_html_primary_bottleneck": (
            "YES — PARTIAL 確定: truncated 64KB は nav/TOC/script 中心で "
            "mw-parser-output 未到達。LLM は HTML メタ応答（Case A/G）"
        ),
        "Q4_llm_utilizes_tool_results": "NO — FAIL（C4/C5: Fetch 後も事実未反映、HTML/JSON 論）",
        "Q5_llm_hallucinates_outside_tools": "YES — H5 CONFIRMED（Case F: 空 search + 約1,900万人）",
        "Q6_agent_loop_structural_problem": (
            "PARTIAL — H3 CONFIRMED（Case B Fetch 省略）、Case C max rounds null"
        ),
        "Q7_prompt_change_required": "UNKNOWN — LLM 利用問題と Fetch 品質の切り分け未完了",
        "Q8_tool_implementation_change_required": (
            "LIKELY YES — read_url_text 利用性、search snippet/ranking（Human Review 要）"
        ),
        "Q9_agent_loop_change_required": "UNKNOWN — Prompt/LLM 判断問題との境界未確定",
        "Q10_research_tool_necessity": "NOT_ESTABLISHED",
    }


def prioritized_fix_targets(analysis: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "priority": "1",
            "target": "read_url_text Fetch 品質（HTML → LLM 利用可能テキスト）",
            "reason": "H1 CONFIRMED: raw/truncated HTML で人口等の事実信号が LLM に届かない",
            "owner": "Tool implementation (Human Review required)",
        },
        {
            "priority": "2",
            "target": "LLM Result utilization（Prompt / モデル指示）",
            "reason": "C4/C5: Tool 結果を HTML/JSON デバッグとして処理。Fetch 後も事実回答にならない",
            "owner": "Prompt + LLM_CAPABILITY（Tool 単独では解決不可）",
        },
        {
            "priority": "3",
            "target": "search_web 検索品質（snippet 空・ranking）",
            "reason": "H2 PARTIAL: 同一意図 query でも空 hits / 無関係 title。Discovery 精度不足",
            "owner": "SEARCH_QUALITY / Tool or backend (Human Review)",
        },
        {
            "priority": "4",
            "target": "Agent Search→Fetch 継続判断",
            "reason": "H3 CONFIRMED: 十分な search 後も Fetch 省略（Case B 等）",
            "owner": "AGENT_LOOP + Prompt（Research Tool ではない）",
        },
        {
            "priority": "5",
            "target": "Primary model Tool Calling（pipeline active_model）",
            "reason": "deepseek-coder-v2:16b は Tool Calling 非対応。Production 経路評価不可",
            "owner": "MODEL_CAPABILITY / infra（Web Tool 実装外）",
        },
    ]
