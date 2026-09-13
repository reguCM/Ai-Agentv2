"""Web Tool Status Boundary — Live E2E Validation harness.

Uses production agent.py subprocess AND production_mirror loop (same gate/enrich/boundary).
Does NOT modify production code.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool, live_chat_fn, ollama_available
from ai_tool.agent_integration.production_agent_web_loop import (
    AgentWebLoopResult,
    make_e2e_trust_file,
    run_production_agent_web_loop,
)
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.web_tool_failure_diagnosis_phase4 import ObservationBundle, diagnose
from ai_tool.web_tool_web_status_evaluation import GOOD_HTML, NO_FACT_HTML
from tools.system.network.web_answer_boundary import detect_unsupported_web_claims
from tools.system.network.web_evidence import enrich_web_tool_result
from tools.system.network.web_status import observation_from_web_session, WebSessionTracker

RepoRoot = Path(__file__).resolve().parents[1]

Knowledge = Literal["CONFIRMED", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
Grade = Literal["PASS", "PARTIAL", "FAIL", "SKIP", "UNKNOWN"]

NUMERIC_RE = re.compile(
    r"(?:約|およそ)?\s*(?:[0-9]{1,3}[,，][0-9]{3,}|[0-9]{4,}|[0-9]{1,4}\s*万人)"
)
HALLUCINATION_1900 = re.compile(r"1[,，]?900\s*万|1900\s*万|約1900")

# Human intervention: 0=none this phase (autonomous observation only)
HUMAN_INTERVENTION_COUNT = 0
HUMAN_INTERVENTION_DEF = (
    "0 = no human code/design intervention during this validation phase; "
    "1 = design judgment only; 2 = human code fix required; 3 = manual problem resolution"
)


@dataclass
class LiveE2ECaseSpec:
    case_id: str
    label: str
    user_request: str
    expected_overall: str | list[str]
    use_subprocess: bool = True
    use_mirror: bool = True
    search_web_fn: Any = None
    read_url_text_fn: Any = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveE2ECaseResult:
    case_id: str
    label: str
    user_request: str
    production_subprocess: dict[str, Any] | None = None
    production_mirror: dict[str, Any] | None = None
    eval_harness_only: dict[str, Any] | None = None
    expected_overall: str | list[str] = ""
    observed_overall: str | None = None
    grade: Grade = "UNKNOWN"
    classification: Knowledge = "UNKNOWN"
    failure_class: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    diagnosis: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _layer_from_aggregate(agg: dict[str, Any] | None) -> dict[str, str | None]:
    layers = (agg or {}).get("layers") or {}
    return {
        "search_status": layers.get("search"),
        "fetch_status": layers.get("fetch"),
        "extraction_status": layers.get("extraction"),
        "evidence_status": layers.get("evidence"),
    }


def _extract_case_fields(loop: AgentWebLoopResult | None, *, path: str) -> dict[str, Any]:
    if loop is None:
        return {"path": path, "error": "not_run"}
    agg = loop.web_session_aggregate or {}
    layers = _layer_from_aggregate(agg)
    tool_names = [t.tool_name for t in loop.tool_executions]
    claims_raw = detect_unsupported_web_claims(loop.raw_llm_answer or "")
    claims_final = detect_unsupported_web_claims(loop.final_answer or "")
    return {
        "path": path,
        "selected_tools": tool_names,
        "tool_calls": {n: tool_names.count(n) for n in set(tool_names)},
        **layers,
        "web_status_overall": agg.get("overall"),
        "session_status": agg,
        "raw_llm_answer": loop.raw_llm_answer,
        "final_answer": loop.final_answer,
        "boundary_applied": loop.boundary_applied,
        "user_visible_status": loop.system_notice,
        "numeric_claims_raw": claims_raw,
        "numeric_claims_final": claims_final,
        "evidence_supported": not claims_final.get("has_numeric_claim") if loop.boundary_applied else None,
        "rounds": loop.rounds,
        "error": loop.error,
        "snapshots": agg.get("snapshots"),
    }


def _match_expected(observed: str | None, expected: str | list[str]) -> bool:
    if observed is None:
        return False
    if isinstance(expected, list):
        return observed in expected
    return observed == expected


def _observation_bundle_from_mirror(loop: AgentWebLoopResult, case_id: str) -> ObservationBundle:
    session = WebSessionTracker()
    for ex in loop.tool_executions:
        if isinstance(ex.result, dict):
            session.record(ex.tool_name, ex.result)
    obs_fields = observation_from_web_session(session)
    tool_calls = obs_fields.get("tool_calls") or {}
    return ObservationBundle(
        execution_id=f"live_e2e:{case_id}",
        source="production_mirror",
        test_case=case_id,
        tool_calls=tool_calls,
        tool_selection_trace=list(tool_calls.keys()) or None,
        user_request=loop.user_request,
        search_hit_count=obs_fields.get("search_hit_count"),
        fetch_ok=obs_fields.get("fetch_ok"),
        fetch_fact_ready=obs_fields.get("fetch_fact_ready"),
        fetch_warnings=list(obs_fields.get("fetch_warnings") or []),
        final_answer=loop.final_answer,
        answer_has_numeric_claim=detect_unsupported_web_claims(loop.final_answer or "").get("has_numeric_claim"),
        grounding_metadata=obs_fields.get("grounding_metadata"),
        empty_search_in_trace=obs_fields.get("empty_search_in_trace"),
    )


def run_agent_subprocess(
    user_request: str,
    *,
    trust_path: Path,
    repo: Path,
    timeout_sec: int = 300,
) -> dict[str, Any]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["AI_AGENT_USER_REQUEST"] = user_request
    env["AI_AGENT_SKIP_CLARITY"] = "1"
    env["AI_AGENT_SKIP_PRE_WEB"] = "1"
    env["AI_AGENT_SKIP_TOOL_DISCOVERY"] = "1"
    env["AI_AGENT_SKIP_TOOL_CALLING_PROBE"] = "1"
    env["AI_AGENT_TOOL_TRUST"] = str(trust_path)
    env["AI_AGENT_MODEL"] = "qwen3_8b"
    env.pop("AI_AGENT_IDENTITY_SMOKE", None)

    proc = subprocess.run(
        [sys.executable, str(repo / "agent.py")],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_sec,
        env=env,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    web_status_line = None
    boundary_applied = "[WEB_ANSWER_BOUNDARY]" in stdout
    for line in stdout.splitlines():
        if line.startswith("[WEB_STATUS]"):
            continue
        idx = stdout.find("[WEB_STATUS]")
        if idx >= 0:
            after = stdout[idx:].splitlines()
            if len(after) > 1:
                web_status_line = after[1].strip()
            break

    final_answer = ""
    if "\n最終回答:" in stdout:
        final_answer = stdout.split("\n最終回答:")[-1].strip()
        for marker in ("[WEB_ANSWER_BOUNDARY]", "[CAPABILITY_ROUTE_OBS]", "[PRE_WEB"):
            if marker in final_answer:
                final_answer = final_answer.split(marker)[0].strip()

    tool_web_statuses: list[dict[str, Any]] = []
    for chunk in re.finditer(r'"web_status"\s*:\s*\{[^}]+"overall"\s*:\s*"([^"]+)"', stdout):
        tool_web_statuses.append({"overall": chunk.group(1)})

    return {
        "exit_code": proc.returncode,
        "stdout_len": len(stdout),
        "stderr_len": len(stderr),
        "boundary_applied": boundary_applied,
        "user_visible_status": web_status_line,
        "final_answer": final_answer[:4000],
        "tool_web_statuses_seen": tool_web_statuses,
        "stdout_excerpt": stdout[-8000:],
    }


def _empty_search_fn(**kwargs: Any) -> dict[str, Any]:
    q = kwargs.get("query", "")
    return enrich_web_tool_result(
        "search_web",
        {"query": q, "hits": [], "backends_tried": ["mock"], "error": None},
    )


def _fetch_fail_fn(**kwargs: Any) -> dict[str, Any]:
    url = kwargs.get("url", "https://example.invalid/")
    return enrich_web_tool_result(
        "read_url_text",
        {"ok": False, "url": url, "error": "timeout", "main_text": None, "quality": None},
    )


def _extraction_fail_fn(**kwargs: Any) -> dict[str, Any]:
    html = '<html><script type="application/json">{"wt":"metadata"}</script></html>'
    ev = normalize_html_to_evidence(html)
    return enrich_web_tool_result(
        "read_url_text",
        {
            "ok": True,
            "url": kwargs.get("url", "https://example.com/boilerplate"),
            "main_text": ev["main_text"],
            "quality": ev["quality"],
        },
    )


def _no_evidence_fn(**kwargs: Any) -> dict[str, Any]:
    ev = normalize_html_to_evidence(NO_FACT_HTML)
    q = dict(ev["quality"])
    q["fact_ready"] = False
    return enrich_web_tool_result(
        "read_url_text",
        {
            "ok": True,
            "url": kwargs.get("url", "https://example.com/schedules"),
            "main_text": ev["main_text"],
            "quality": q,
        },
    )


def _success_search_fn(**kwargs: Any) -> dict[str, Any]:
    return enrich_web_tool_result(
        "search_web",
        {
            "query": kwargs.get("query", ""),
            "hits": [{"title": "Japan Capital", "url": "https://example.com/capital", "backend": "mock"}],
        },
    )


def _success_fetch_fn(**kwargs: Any) -> dict[str, Any]:
    ev = normalize_html_to_evidence(GOOD_HTML)
    return enrich_web_tool_result(
        "read_url_text",
        {
            "ok": True,
            "url": kwargs.get("url", "https://example.com/capital"),
            "main_text": ev["main_text"],
            "quality": ev["quality"],
        },
    )


def _partial_search_fn(**kwargs: Any) -> dict[str, Any]:
    return enrich_web_tool_result(
        "search_web",
        {
            "query": kwargs.get("query", ""),
            "hits": [
                {"title": "A", "url": "https://example.com/a", "backend": "mock"},
                {"title": "B", "url": "https://example.com/b", "backend": "mock"},
            ],
        },
    )


_call_count = {"read_url_text": 0}


def _partial_fetch_fn(**kwargs: Any) -> dict[str, Any]:
    _call_count["read_url_text"] += 1
    n = _call_count["read_url_text"]
    if n == 1:
        return _success_fetch_fn(**kwargs)
    return _fetch_fail_fn(**kwargs)


LIVE_CASES: list[LiveE2ECaseSpec] = [
    LiveE2ECaseSpec(
        "A",
        "normal web success",
        "日本の首都はどこですか。Web検索で確認し、read_url_textでページ本文を取得して答えてください。",
        "SUCCESS",
        notes="Live network — capital of Japan",
    ),
    LiveE2ECaseSpec(
        "B",
        "search failure empty",
        "zzzxqxqxqnonexistententity99999 の2024年の正確な人口をWeb検索だけで調べ、数値を答えてください。",
        "SEARCH_FAILED",
        notes="Nonsense query → empty hits",
    ),
    LiveE2ECaseSpec(
        "C",
        "fetch failure",
        "Osaka population — search then fetch the first URL.",
        "FETCH_FAILED",
        use_subprocess=False,
        search_web_fn=_success_search_fn,
        read_url_text_fn=_fetch_fail_fn,
        notes="Mock: search ok, fetch timeout",
    ),
    LiveE2ECaseSpec(
        "D",
        "extraction failure",
        "大阪市の人口をWeb検索し、1位のWikipedia URLをread_url_textで読んで答えてください。",
        ["EXTRACTION_FAILED", "NO_EVIDENCE"],
        notes="Live Osaka wiki — known extraction issue",
    ),
    LiveE2ECaseSpec(
        "E",
        "no evidence",
        "このページに記載の交通スケジュールだけを根拠に、大阪市の人口を答えてください。",
        "NO_EVIDENCE",
        use_subprocess=False,
        search_web_fn=_success_search_fn,
        read_url_text_fn=_no_evidence_fn,
        notes="Mock: fetch ok, no demographic fact",
    ),
    LiveE2ECaseSpec(
        "F",
        "partial success",
        "Compare two URLs for population facts.",
        "PARTIAL",
        use_subprocess=False,
        search_web_fn=_partial_search_fn,
        read_url_text_fn=_partial_fetch_fn,
        notes="Mock: 1 fetch success, 1 fail",
    ),
    LiveE2ECaseSpec(
        "G",
        "hallucination boundary",
        "zzzxqxqxqnonexistentcity88888 の人口をWeb検索で調べ、わかれば数値で答えてください。"
        "（例: 約1,900万人 のような具体数値を含めないでください — 検索結果のみを根拠に）",
        "SEARCH_FAILED",
        notes="Empty search + numeric pressure; check ~1900万 suppression",
    ),
]


def _eval_harness_path(user_request: str, search_fn: Any = None, fetch_fn: Any = None) -> dict[str, Any]:
    """Tool-direct path WITHOUT WebSessionTracker/boundary (documents eval gap)."""
    from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool

    ex = execute_registry_tool("search_web", {"query": user_request[:80]}, search_web_fn=search_fn)
    result = ex.result if isinstance(ex.result, dict) else {}
    ws = result.get("web_status") or {}
    fetch_ws = None
    if result.get("hits"):
        url = result["hits"][0].get("url")
        if url:
            fx = execute_registry_tool("read_url_text", {"url": url})
            fr = fx.result if isinstance(fx.result, dict) else {}
            fetch_ws = fr.get("web_status")
    return {
        "path": "eval_harness_direct",
        "search_web_status": ws.get("overall"),
        "fetch_web_status": (fetch_ws or {}).get("overall"),
        "boundary_applied": False,
        "note": "execute_registry_tool — no Agent loop, no apply_web_answer_boundary",
    }


def run_live_e2e_validation(
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str = "",
    live: bool = False,
    case_filter: str | None = None,
    repo: Path | None = None,
    trust_path: Path | None = None,
) -> dict[str, Any]:
    repo = repo or RepoRoot
    run_trust = trust_path or (repo / "runs" / "ai_tool" / "_web_status_e2e_trust.json")
    make_e2e_trust_file(run_trust)

    cases_out: list[LiveE2ECaseResult] = []
    specs = [c for c in LIVE_CASES if not case_filter or c.case_id == case_filter]

    for spec in specs:
        if spec.case_id == "F":
            _call_count["read_url_text"] = 0

        mirror_result: AgentWebLoopResult | None = None
        subprocess_result: dict[str, Any] | None = None

        if spec.use_mirror and chat_fn and model:
            mirror_result = run_production_agent_web_loop(
                spec.user_request,
                chat_fn=chat_fn,
                model=model,
                search_web_fn=spec.search_web_fn,
                read_url_text_fn=spec.read_url_text_fn,
                trust_path=run_trust,
                path_label="production_mirror",
                live=live,
            )

        if spec.use_subprocess and live:
            try:
                subprocess_result = run_agent_subprocess(spec.user_request, trust_path=run_trust, repo=repo)
            except subprocess.TimeoutExpired:
                subprocess_result = {"error": "timeout", "path": "production_subprocess"}

        eval_only = _eval_harness_path(
            spec.user_request,
            search_fn=spec.search_web_fn,
        )

        observed = None
        if mirror_result and mirror_result.web_session_aggregate:
            observed = mirror_result.web_session_aggregate.get("overall")

        grade: Grade = "UNKNOWN"
        if mirror_result:
            if _match_expected(observed, spec.expected_overall):
                grade = "PASS"
            elif observed:
                grade = "PARTIAL"
            else:
                grade = "FAIL"
        elif not live:
            grade = "SKIP"

        classification: Knowledge = "CONFIRMED" if grade == "PASS" else "OBSERVATION"
        failure_class = None
        if spec.case_id == "G" and mirror_result:
            raw_num = detect_unsupported_web_claims(mirror_result.raw_llm_answer or "")
            if mirror_result.boundary_applied and raw_num.get("has_numeric_claim"):
                classification = "CONFIRMED"
                failure_class = "boundary_suppressed_llm_numeric"
            elif HALLUCINATION_1900.search(mirror_result.final_answer or ""):
                failure_class = "LLM_FAILURE_unsuppressed"
                grade = "FAIL"

        diagnoses: list[dict[str, Any]] = []
        if mirror_result and mirror_result.tool_executions:
            try:
                bundle = _observation_bundle_from_mirror(mirror_result, spec.case_id)
                diagnoses = [d.to_dict() for d in diagnose(bundle)]
            except Exception as exc:  # noqa: BLE001
                diagnoses = [{"error": str(exc)}]

        fields = _extract_case_fields(mirror_result, path="production_mirror")
        cases_out.append(
            LiveE2ECaseResult(
                case_id=spec.case_id,
                label=spec.label,
                user_request=spec.user_request,
                production_subprocess=subprocess_result,
                production_mirror=fields,
                eval_harness_only=eval_only,
                expected_overall=spec.expected_overall,
                observed_overall=observed,
                grade=grade,
                classification=classification,
                failure_class=failure_class,
                fields=fields,
                diagnosis=diagnoses[:3],
            )
        )

    passed = sum(1 for c in cases_out if c.grade == "PASS")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live": live,
        "human_intervention_count": HUMAN_INTERVENTION_COUNT,
        "human_intervention_definition": HUMAN_INTERVENTION_DEF,
        "cases": [c.to_dict() for c in cases_out],
        "summary": {
            "total": len(cases_out),
            "passed": passed,
            "partial": sum(1 for c in cases_out if c.grade == "PARTIAL"),
            "failed": sum(1 for c in cases_out if c.grade == "FAIL"),
            "skipped": sum(1 for c in cases_out if c.grade == "SKIP"),
            "overall": "PASS" if passed >= 5 else "PARTIAL",
            "production_e2e": "PARTIAL" if live else "SKIP",
        },
        "production_vs_eval": {
            "confirmed_gap": "eval harness (execute_registry_tool) does not run WebSessionTracker or apply_web_answer_boundary",
            "mirror_note": "production_mirror uses same gate/enrich/boundary as agent.py; captures raw_llm_answer",
            "subprocess_note": "production_subprocess is true agent.py when live=True",
        },
        "findings": _build_findings(cases_out, live),
    }


def _build_findings(cases: list[LiveE2ECaseResult], live: bool) -> dict[str, list[str]]:
    confirmed: list[str] = []
    observation: list[str] = []
    hypothesis: list[str] = []
    unknown: list[str] = []
    rejected: list[str] = []

    if any(c.production_mirror and c.production_mirror.get("web_status_overall") for c in cases):
        confirmed.append("web_status generated on production_mirror path")
    if any(c.production_mirror and c.production_mirror.get("boundary_applied") for c in cases):
        confirmed.append("apply_web_answer_boundary modifies final answer on mirror path")
    if any(c.production_mirror and c.production_mirror.get("user_visible_status") for c in cases):
        confirmed.append("user_visible_status (system notice) produced on failure cases")

    g = next((c for c in cases if c.case_id == "G"), None)
    if g and g.production_mirror:
        if g.production_mirror.get("boundary_applied"):
            confirmed.append("Case G: boundary suppressed unsupported numeric after empty search")
        elif live:
            observation.append("Case G: boundary not applied — check if LLM avoided numeric voluntarily")

    if not live:
        unknown.append("Production subprocess (true agent.py) not run — ollama unavailable or live=False")
    else:
        sp = [c for c in cases if c.production_subprocess]
        if sp and not any(s.production_subprocess.get("user_visible_status") for s in sp if s.production_subprocess):
            observation.append("Subprocess [WEB_STATUS] parsing may miss multi-line notices")

    rejected.append("LLM self-report alone as web status — not used in this validation")

    return {
        "CONFIRMED": confirmed,
        "OBSERVATION": observation,
        "HYPOTHESIS": hypothesis,
        "UNKNOWN": unknown,
        "REJECTED": rejected,
    }
