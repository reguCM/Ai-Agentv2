"""Web Tool Failure Isolation Phase 3 — read-only investigation harness."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.read_url.reader import read_url_text
from tools.system.network import general_web_search as gws
from tools.system.network.search_web import search_web

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
Layer = Literal["Search", "Agent", "LLM", "Fetch", "Prompt", "UNKNOWN"]
Classification = Literal["CONFIRMED FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN", "DESIGN PROPOSAL"]

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE1_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_201538_web_tool_practical_evaluation"
PHASE2_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_214841_web_tool_practical_evaluation_phase2"

# General fact queries — not Osaka-only
SEARCH_ISOLATION_QUERIES: list[tuple[str, str, str | None]] = [
    ("大阪市 人口", "ja_fact_osaka_space", "大阪市"),
    ("大阪市の人口", "ja_fact_osaka_no", "大阪市"),
    ("東京 人口", "ja_fact_tokyo", "東京"),
    ("富士山 高さ", "ja_fact_fuji", "富士山"),
    ("Python programming language", "en_fact_python", "Python"),
    ("Paris population", "en_fact_paris", "Paris"),
    ("日本 首都", "ja_fact_capital", "首都"),
    ("this-query-should-return-nothing-xyz123", "empty_control", None),
]

HALLUCINATION_NUMERIC = re.compile(r"(?:約|推計)?\s*[0-9]{1,3}[,，]?[0-9]{3,}\s*(?:万人|人)?")
HTML_META_MARKERS = ("HTML", "BeautifulSoup", "パーサー", "JSONデータ", "トリミング", "DOCTYPE")


@dataclass
class SearchIsolationRow:
    query: str
    label: str
    expected_entity: str | None
    per_backend: dict[str, list[dict[str, Any]]]
    per_backend_errors: dict[str, str]
    raw_collected_count: int
    pre_rank_top: list[dict[str, Any]]
    post_rank_hits: list[dict[str, Any]]
    post_rank_scored: list[dict[str, Any]]
    hit_count: int
    first_hit_relevant: bool | None
    classification: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentLoopRow:
    case_id: str
    source_run: str
    prompt_variant: str
    user_request: str
    search_calls: int
    fetch_calls: int
    final_answer_null: bool
    post_search_decision: str
    fetch_explicitly_requested: bool
    had_usable_search_hit: bool
    llm_selected_fetch: bool
    agent_blocked_fetch: bool
    evidence: dict[str, Any]
    classification: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hit_relevant(hit: dict[str, Any], expected: str | None) -> bool | None:
    if expected is None:
        return None
    title = str(hit.get("title") or "")
    url = str(hit.get("url") or "")
    blob = f"{title} {url}".lower()
    exp = expected.lower()
    if exp in title or exp in blob:
        if hit.get("relevance_hint") == "low":
            return False
        return True
    return False


def probe_search_isolation(query: str, label: str, expected: str | None) -> SearchIsolationRow:
    backends = (
        ("duckduckgo", gws.search_duckduckgo),
        ("wikipedia-ja", gws.search_wikipedia),
        ("wikipedia-en", gws.search_wikipedia_en),
    )
    per_backend: dict[str, list] = {}
    per_backend_errors: dict[str, str] = {}
    collected: list[dict] = []
    for name, fn in backends:
        try:
            hits = list(fn(query, limit=5))
            per_backend[name] = hits
            collected.extend(hits)
        except Exception as exc:  # noqa: BLE001
            per_backend[name] = []
            per_backend_errors[name] = f"{type(exc).__name__}: {exc}"

    unique = gws.unique_hits(collected)
    tokens = gws.query_tokens(query)
    pre_scored = [(gws.score_hit_for_query(h, query, tokens), h) for h in unique]
    pre_scored.sort(key=lambda x: x[0], reverse=True)
    pre_rank_top = [{"score": s, **h} for s, h in pre_scored[:5]]

    tool_result = search_web(query, limit=5)
    post_hits = tool_result.get("hits") or []
    _, post_scored_raw = gws.rank_hits_for_query(unique, query, limit=5)
    post_scored = [{"score": s, **h} for s, h in post_scored_raw[:10]]

    first_rel = None
    if post_hits and expected:
        first_rel = _hit_relevant(post_hits[0], expected)

    cls: dict[str, str] = {}
    if not post_hits and not any(per_backend.values()):
        cls["primary"] = "A2_backend_empty_or_query_no_match"
    elif per_backend.get("wikipedia-ja") and not _any_backend_has_entity(per_backend, expected):
        cls["primary"] = "A2_backend_prefix_match_not_entity"
    elif pre_scored and pre_scored[0][0] <= 0:
        cls["primary"] = "A3_ranking_all_zero_score"
    elif first_rel is False:
        cls["primary"] = "A3_ranking_irrelevant_first"
    elif first_rel is True:
        cls["primary"] = "search_ok_at_tool_layer"
    else:
        cls["primary"] = "UNKNOWN"

    return SearchIsolationRow(
        query=query,
        label=label,
        expected_entity=expected,
        per_backend=per_backend,
        per_backend_errors=per_backend_errors,
        raw_collected_count=len(unique),
        pre_rank_top=pre_rank_top,
        post_rank_hits=post_hits,
        post_rank_scored=post_scored,
        hit_count=len(post_hits),
        first_hit_relevant=first_rel,
        classification=cls,
    )


def _any_backend_has_entity(per_backend: dict, expected: str | None) -> bool:
    if not expected:
        return False
    for hits in per_backend.values():
        for h in hits:
            if expected in str(h.get("title") or ""):
                return True
    return False


def _fetch_explicitly_requested(user_request: str) -> bool:
    markers = ("読んで", "本文", "ページの内容", "fetch", "read_url")
    return any(m in user_request for m in markers)


def _had_usable_hit(tool_results: list[dict]) -> bool:
    for r in tool_results:
        if not isinstance(r, dict) or "hits" not in r:
            continue
        for h in r.get("hits") or []:
            if isinstance(h, dict) and h.get("relevance_hint") in ("high", "medium"):
                return True
            if isinstance(h, dict) and str(h.get("title") or "").startswith("大阪市"):
                if "の" not in str(h.get("title") or "")[:6]:
                    return True
    return False


def _classify_post_search_decision(
    *,
    search_calls: int,
    fetch_calls: int,
    final_answer: str | None,
    tool_call_count: int,
    max_rounds_reached: bool = False,
) -> str:
    if fetch_calls > 0:
        return "FETCH_SELECTED"
    if search_calls > 1 and fetch_calls == 0:
        return "RESEARCH_WITHOUT_FETCH"
    if search_calls >= 1 and fetch_calls == 0 and final_answer:
        return "ANSWER_WITHOUT_FETCH"
    if search_calls >= 1 and fetch_calls == 0 and not final_answer:
        return "STOP_WITHOUT_ANSWER"
    if tool_call_count == 0:
        return "NO_TOOLS"
    return "UNKNOWN"


def analyze_live_trace(case: dict[str, Any], *, source_run: str, prompt_variant: str) -> AgentLoopRow:
    tools = case.get("selected_tools") or []
    sw = tools.count("search_web")
    ru = tools.count("read_url_text")
    user_request = str(case.get("user_request") or "")
    final = case.get("final_answer")
    tool_results = case.get("tool_results") or []
    fetch_req = _fetch_explicitly_requested(user_request)
    usable = _had_usable_hit(tool_results)

    post = _classify_post_search_decision(
        search_calls=sw,
        fetch_calls=ru,
        final_answer=final,
        tool_call_count=int(case.get("tool_call_count") or 0),
        max_rounds_reached=sw >= 5,
    )

    # Eval harness: execute_registry_tool always runs LLM-selected tools — no Agent block layer
    agent_blocked = False
    llm_selected_fetch = ru > 0

    cls: dict[str, str] = {}
    if post == "ANSWER_WITHOUT_FETCH" and fetch_req:
        cls["fetch_skip_cause"] = "HYPOTHESIS_LLM_DID_NOT_SELECT_FETCH"
    elif post == "FETCH_SELECTED":
        cls["fetch_skip_cause"] = "NOT_APPLICABLE"
    elif post == "RESEARCH_WITHOUT_FETCH":
        cls["fetch_skip_cause"] = "HYPOTHESIS_LLM_PREFERRED_RESEARCH"
    else:
        cls["fetch_skip_cause"] = "UNKNOWN"

    return AgentLoopRow(
        case_id=str(case.get("case_id") or ""),
        source_run=source_run,
        prompt_variant=prompt_variant,
        user_request=user_request,
        search_calls=sw,
        fetch_calls=ru,
        final_answer_null=final is None,
        post_search_decision=post,
        fetch_explicitly_requested=fetch_req,
        had_usable_search_hit=usable,
        llm_selected_fetch=llm_selected_fetch,
        agent_blocked_fetch=agent_blocked,
        evidence={
            "queries": [a.get("query") for a in (case.get("tool_arguments") or []) if "query" in (a or {})],
            "html_meta_answer": _has_html_meta(final),
            "hallucination_numeric": _has_hallucination(final, tool_results),
            "any_fact_ready": _any_fact_ready(tool_results),
        },
        classification=cls,
    )


def _has_html_meta(answer: Any) -> bool:
    if not answer:
        return False
    return any(m in str(answer) for m in HTML_META_MARKERS)


def _has_hallucination(answer: Any, tool_results: list) -> bool:
    if not answer:
        return False
    empty_search = any(
        isinstance(r, dict) and "hits" in r and not (r.get("hits") or []) for r in tool_results
    )
    if not empty_search:
        return False
    text = str(answer)
    if HALLUCINATION_NUMERIC.search(text) and "確認でき" not in text and "提供できません" not in text:
        return True
    return False


def _any_fact_ready(tool_results: list) -> bool:
    for r in tool_results:
        if isinstance(r, dict) and r.get("quality", {}).get("fact_ready"):
            return True
    return False


def load_live_cases(run_dir: Path, prompt_variant: str) -> list[AgentLoopRow]:
    if not run_dir.is_dir():
        return []
    rows: list[AgentLoopRow] = []
    for path in sorted(run_dir.glob("case_*_live*.json")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(analyze_live_trace(case, source_run=run_dir.name, prompt_variant=prompt_variant))
    return rows


def probe_fetch_for_urls(urls: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for url in urls[:8]:
        try:
            r = read_url_text(url)
        except Exception as exc:  # noqa: BLE001
            r = {"ok": False, "error": str(exc)}
        quality = r.get("quality") if isinstance(r, dict) else {}
        out.append(
            {
                "url": url,
                "ok": r.get("ok") if isinstance(r, dict) else False,
                "fact_ready": (quality or {}).get("fact_ready") if isinstance(quality, dict) else None,
                "body_reached": (quality or {}).get("body_reached") if isinstance(quality, dict) else None,
                "main_text_len": len(str(r.get("main_text") or "")) if isinstance(r, dict) else 0,
                "warnings": (quality or {}).get("warnings") if isinstance(quality, dict) else [],
            }
        )
    return out


def analyze_prompt_contribution(phase1_rows: list[AgentLoopRow], phase2_rows: list[AgentLoopRow]) -> dict[str, Any]:
    def metrics(rows: list[AgentLoopRow]) -> dict[str, Any]:
        return {
            "case_count": len(rows),
            "total_fetch_calls": sum(r.fetch_calls for r in rows),
            "fetch_rate": sum(1 for r in rows if r.fetch_calls > 0) / max(len(rows), 1),
            "answer_without_fetch": sum(1 for r in rows if r.post_search_decision == "ANSWER_WITHOUT_FETCH"),
            "html_meta": sum(1 for r in rows if r.evidence.get("html_meta_answer")),
            "hallucination": sum(1 for r in rows if r.evidence.get("hallucination_numeric")),
        }

    p1 = metrics(phase1_rows)
    p2 = metrics(phase2_rows)
    return {
        "phase1_detailed_prompt": p1,
        "phase2_minimal_prompt": p2,
        "observations": [
            {
                "type": "OBSERVATION",
                "note": "Phase1 fetch_rate > Phase2 fetch_rate",
                "value": p1["fetch_rate"] > p2["fetch_rate"],
            },
            {
                "type": "OBSERVATION",
                "note": "Phase1 html_meta count vs Phase2",
                "phase1": p1["html_meta"],
                "phase2": p2["html_meta"],
            },
        ],
        "classification": {
            "prompt_can_fix_fetch_selection": "HYPOTHESIS_PARTIAL",
            "prompt_can_fix_search_quality": "HYPOTHESIS_NO",
            "prompt_can_fix_fact_ready": "HYPOTHESIS_NO",
        },
    }


def llm_capability_matrix(rows: list[AgentLoopRow]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for r in rows:
        ev = r.evidence
        if r.search_calls == 0:
            bucket = "NO_SEARCH"
        elif not ev.get("any_fact_ready") and r.fetch_calls == 0 and r.post_search_decision == "ANSWER_WITHOUT_FETCH":
            bucket = "UNDERSTANDS_SEARCH_SKIPS_FETCH" if _had_usable_hit_from_row(r) else "SEARCH_POOR_OR_MISUNDERSTOOD"
        elif r.fetch_calls > 0 and not ev.get("any_fact_ready") and ev.get("html_meta_answer"):
            bucket = "FETCH_BUT_META_RESPONSE"
        elif r.fetch_calls > 0 and not ev.get("any_fact_ready"):
            bucket = "FETCH_NON_FACT_READY"
        elif ev.get("hallucination_numeric"):
            bucket = "HALLUCINATES_ON_EMPTY"
        elif r.final_answer_null:
            bucket = "NO_FINAL_ANSWER"
        else:
            bucket = "GROUNDED_OR_UNCERTAIN_OK"
        matrix.append({"case_id": r.case_id, "prompt": r.prompt_variant, "bucket": bucket, "source": r.source_run})
    return matrix


def _had_usable_hit_from_row(row: AgentLoopRow) -> bool:
    return row.had_usable_search_hit


def build_root_cause_table(
    search_rows: list[SearchIsolationRow],
    agent_rows: list[AgentLoopRow],
    fetch_probes: list[dict[str, Any]],
    prompt_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []

    irrelevant_first = sum(1 for r in search_rows if r.first_hit_relevant is False)
    if irrelevant_first:
        table.append(
            {
                "problem": "First hit often irrelevant for variant queries (e.g. の-insertion)",
                "layer": "Search",
                "evidence": f"{irrelevant_first}/{len([r for r in search_rows if r.expected_entity])} probes first_hit_relevant=false",
                "confidence": "HIGH",
                "impact": "HIGH",
                "proposed_next_action": "PROPOSED CHANGE: ranking/backend review (Human Review)",
            }
        )

    ddg_empty = sum(1 for r in search_rows if not r.per_backend.get("duckduckgo"))
    if ddg_empty:
        table.append(
            {
                "problem": "duckduckgo returns empty across probes",
                "layer": "Search",
                "evidence": f"empty in {ddg_empty}/{len(search_rows)} probes",
                "confidence": "HIGH",
                "impact": "MEDIUM",
                "proposed_next_action": "PROPOSED CHANGE: backend availability investigation",
            }
        )

    fetch_skip_explicit = [
        r for r in agent_rows if r.fetch_explicitly_requested and r.fetch_calls == 0
    ]
    if fetch_skip_explicit:
        table.append(
            {
                "problem": "LLM skips Fetch despite explicit user request",
                "layer": "LLM",
                "evidence": f"cases {[r.case_id for r in fetch_skip_explicit]} eval harness — no Agent block observed",
                "confidence": "HIGH",
                "impact": "HIGH",
                "proposed_next_action": "PROPOSED CHANGE: Agent fetch gate OR stronger contract (Human Review)",
            }
        )

    if all(not p.get("fact_ready") for p in fetch_probes if p.get("ok")):
        table.append(
            {
                "problem": "Fetched Wikipedia pages fact_ready=false in probes",
                "layer": "Fetch",
                "evidence": "fetch probes on search top URLs",
                "confidence": "MEDIUM",
                "impact": "MEDIUM",
                "proposed_next_action": "PROPOSED CHANGE: extraction quality (Human Review)",
            }
        )

    halluc = [r for r in agent_rows if r.evidence.get("hallucination_numeric")]
    if halluc:
        table.append(
            {
                "problem": "Numeric supplementation after empty search",
                "layer": "LLM",
                "evidence": f"cases {[r.case_id for r in halluc]}",
                "confidence": "MEDIUM",
                "impact": "HIGH",
                "proposed_next_action": "PROPOSED CHANGE: Agent grounding enforce in production loop",
            }
        )

    p1_rate = (prompt_analysis.get("phase1_detailed_prompt") or {}).get("fetch_rate", 0)
    p2_rate = (prompt_analysis.get("phase2_minimal_prompt") or {}).get("fetch_rate", 0)
    if p1_rate > p2_rate:
        table.append(
            {
                "problem": "Detailed prompt increases fetch rate vs minimal",
                "layer": "Prompt",
                "evidence": f"fetch_rate phase1={p1_rate:.2f} phase2={p2_rate:.2f}",
                "confidence": "HIGH",
                "impact": "MEDIUM",
                "proposed_next_action": "Keep contract-based prompt hints; prompt alone insufficient for utilization",
            }
        )

    eval_no_enforce = {
        "type": "CONFIRMED FACT",
        "note": "Practical eval uses execute_registry_tool — LLM tool selection equals execution; Agent enforcement not in eval path",
    }
    table.append(
        {
            "problem": "Agent grounding metadata exists but eval path has no enforcement",
            "layer": "Agent",
            "evidence": str(eval_no_enforce),
            "confidence": "HIGH",
            "impact": "MEDIUM",
            "proposed_next_action": "PROPOSED CHANGE: distinguish production agent.py vs eval harness in future tests",
        }
    )

    return table


def build_proposed_options(table: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "Option A": {
            "title": "Search layer hardening only",
            "targets": ["ranking", "backend coverage", "snippet"],
            "does_not_target": ["LLM fetch selection", "Agent enforce"],
            "side_effects": "May overfit Wikipedia prefix matching",
            "safety": "LOW risk",
            "implementation_scale": "MEDIUM",
            "automation_fit": "HIGH — tool-only probes",
            "remaining_unknown": "DDG empty root cause (network vs API)",
        },
        "Option B": {
            "title": "Agent loop policy (fetch gate + empty-search block)",
            "targets": ["Fetch skip", "hallucination on empty search"],
            "does_not_target": ["Search ranking", "Fetch extraction"],
            "side_effects": "Over-fetch on bad hits; needs fact_ready check",
            "safety": "MEDIUM — must not bypass SSRF",
            "implementation_scale": "SMALL-MEDIUM",
            "automation_fit": "MEDIUM — needs production agent tests",
            "remaining_unknown": "Optimal gate conditions without over-fetch",
        },
        "Option C": {
            "title": "Fetch extraction + evidence quality",
            "targets": ["fact_ready=false on Wikipedia", "main_text usability"],
            "does_not_target": ["LLM query generation", "Search ranking"],
            "side_effects": "Site-specific extraction maintenance",
            "safety": "LOW-MEDIUM",
            "implementation_scale": "MEDIUM",
            "automation_fit": "HIGH — fixture HTML tests",
            "remaining_unknown": "JS-rendered pages",
        },
    }


def build_automation_insights() -> list[dict[str, Any]]:
    return [
        {
            "symptom": "Fetch not executed",
            "required_observation": ["selected_tools", "user_request fetch markers", "search hits relevance_hint"],
            "decision_rule": "IF fetch_explicit AND search_calls>=1 AND fetch_calls==0 THEN layer=LLM (eval) OR Agent (prod if blocked)",
            "possible_action": "PROPOSED: fetch gate or prompt contract",
            "human_review_required": True,
        },
        {
            "symptom": "Wrong first search hit",
            "required_observation": ["query", "per_backend hits", "pre_rank scores", "post_rank first title"],
            "decision_rule": "IF backend has correct title BUT ranked first is wrong THEN layer=Search ranking",
            "possible_action": "PROPOSED: ranking change",
            "human_review_required": True,
        },
        {
            "symptom": "Hallucinated population number",
            "required_observation": ["empty_search in tool_results", "final_answer numeric regex", "grounding flags"],
            "decision_rule": "IF empty_search AND numeric_in_answer AND NOT uncertainty_phrase THEN layer=LLM",
            "possible_action": "PROPOSED: Agent block",
            "human_review_required": True,
        },
        {
            "symptom": "fact_ready=false after fetch",
            "required_observation": ["quality.fact_ready", "quality.warnings", "main_text_len"],
            "decision_rule": "IF ok AND NOT fact_ready THEN layer=Fetch",
            "possible_action": "PROPOSED: extraction",
            "human_review_required": True,
        },
    ]


def run_failure_isolation() -> dict[str, Any]:
    search_rows = [probe_search_isolation(q, lbl, exp) for q, lbl, exp in SEARCH_ISOLATION_QUERIES]

    phase1_rows = load_live_cases(PHASE1_RUN, "detailed")
    phase2_rows = load_live_cases(PHASE2_RUN, "minimal")
    agent_rows = phase1_rows + phase2_rows

    # Fetch probes on URLs from good vs bad search queries
    good_urls: list[str] = []
    bad_urls: list[str] = []
    for row in search_rows:
        if row.first_hit_relevant is True and row.post_rank_hits:
            good_urls.append(str(row.post_rank_hits[0].get("url") or ""))
        elif row.first_hit_relevant is False and row.post_rank_hits:
            bad_urls.append(str(row.post_rank_hits[0].get("url") or ""))
    fetch_probes = probe_fetch_for_urls([u for u in good_urls + bad_urls if u.startswith("http")])

    prompt_analysis = analyze_prompt_contribution(phase1_rows, phase2_rows)
    llm_matrix = llm_capability_matrix(agent_rows)
    root_causes = build_root_cause_table(search_rows, agent_rows, fetch_probes, prompt_analysis)
    options = build_proposed_options(root_causes)
    automation = build_automation_insights()

    return {
        "search_isolation": [r.to_dict() for r in search_rows],
        "agent_loop": [r.to_dict() for r in agent_rows],
        "fetch_isolation": fetch_probes,
        "prompt_contribution": prompt_analysis,
        "llm_capability_matrix": llm_matrix,
        "root_cause_table": root_causes,
        "proposed_options": options,
        "automation_loop_insights": automation,
    }


def domain_status(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    search_rows = analysis.get("search_isolation") or []
    bad_first = sum(1 for r in search_rows if r.get("first_hit_relevant") is False)
    return {
        "SEARCH": {
            "status": "FAIL" if bad_first >= 2 else "PARTIAL",
            "confirmed": ["backend-specific empty hits", "ranking irrelevant first hit on の-variant queries"],
            "unknown": ["DDG failure mode (transient vs policy)"],
        },
        "AGENT": {
            "status": "PARTIAL",
            "confirmed": ["eval path has no fetch enforcement", "grounding metadata attached only"],
            "unknown": ["production agent.py behavior under same cases without live re-run"],
        },
        "LLM": {
            "status": "FAIL",
            "confirmed": ["fetch skip on explicit request (Case B)", "hallucination on empty search (Case C/F traces)"],
            "unknown": ["whether qwen3 would fetch with production agent.py prompt"],
        },
        "FETCH": {
            "status": "PARTIAL",
            "confirmed": ["fact_ready=false on Wikipedia probe URLs", "fetch not reached in phase2 live"],
            "unknown": ["fact_ready rate on non-Wikipedia sources"],
        },
        "PROMPT": {
            "status": "PARTIAL",
            "confirmed": ["detailed prompt increases fetch rate vs minimal", "prompt did not fix HTML meta alone (phase1)"],
            "unknown": ["optimal minimal contract wording"],
        },
    }
