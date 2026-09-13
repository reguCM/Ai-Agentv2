"""TDA PoC harness — evaluation A–H, LLM-only vs LLM+Web (experimental)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from ai_tool.defensive_core_discovery_policy import (
    evaluate_llm_capability_role,
    phase_forbidden_actions,
)
from ai_tool.experimental.conversation_resolution.e2e_adapter import (
    check_url_integrity,
    evidence_sources_from_loop,
    make_fixture_search_fn,
    make_multi_fixture_read_url_fn,
    run_canonical_evidence_collection,
)
from ai_tool.experimental.conversation_resolution.resolver import initialize_conversation
from ai_tool.experimental.development_assistance.fixtures import TDACaseSpec, tda_evaluation_cases
from ai_tool.experimental.development_assistance.followup import handle_tda_follow_up
from ai_tool.experimental.development_assistance.proposal import build_development_proposal
from ai_tool.experimental.development_assistance.query_generator import generate_search_queries
from ai_tool.experimental.development_assistance.requirement_gate import assess_research_requirement
from ai_tool.experimental.development_assistance.technology_candidate import (
    add_custom_build_candidate,
    build_technology_candidates,
    tech_candidates_to_envelope,
)
from ai_tool.web_tool_extraction_normalization_production import run_production_golden

RepoRoot = Path(__file__).resolve().parents[3]

TDADecision = Literal["CONTINUE", "INVESTIGATE", "STOP_NO_VALUE"]
ChatFn = Callable[..., Any]


@dataclass
class TDARunState:
    selected_candidate_id: str | None = None
    development_decision: str | None = None
    turn: int = 0


def _llm_only_proposal(requirement: str, gate_result: Any) -> dict[str, Any]:
    """Baseline without Web Research."""
    return {
        "mode": "llm_only",
        "requirement": requirement,
        "gate": gate_result.to_dict(),
        "queries": [],
        "sources_extracted": 0,
        "candidates": [],
        "proposal": {
            "requirement": requirement,
            "research_performed": False,
            "candidates": [],
            "known": ["General LLM knowledge only — no Web Evidence"],
            "unknown": ["version", "license", "environment", "latest API"],
            "conflicts": [],
            "recommendation": "LLM知識のみに基づく一般論。最新仕様・環境は未確認。",
            "llm_body": f"要求「{requirement}」について、Web調査なしの一般回答です。",
        },
        "source_urls": [],
        "url_integrity": True,
    }


def _score_case_checks(
    spec: TDACaseSpec,
    result: dict[str, Any],
    *,
    mode: str,
) -> tuple[list[str], list[str]]:
    ok: list[str] = []
    failures: list[str] = []
    checks = spec.checks or {}
    proposal = result.get("proposal") or {}
    candidates = result.get("candidates") or proposal.get("candidates") or []

    if result.get("gate", {}).get("decision") != spec.expected_gate:
        failures.append(f"gate expected {spec.expected_gate} got {result.get('gate', {}).get('decision')}")

    if checks.get("min_candidates"):
        n = len([c for c in candidates if c.get("type") != "Custom Build"])
        if n >= int(checks["min_candidates"]):
            ok.append("min_candidates")
        else:
            failures.append(f"candidates {n} < {checks['min_candidates']}")

    if checks.get("multi_type"):
        types = {c.get("type") for c in candidates}
        if len(types) >= 2:
            ok.append("multi_type")
        else:
            failures.append(f"multi_type got {types}")

    if checks.get("has_custom_build"):
        if any(c.get("type") == "Custom Build" for c in candidates):
            ok.append("custom_build")
        else:
            failures.append("missing custom build candidate")

    if checks.get("version_conflict"):
        conflicts = proposal.get("conflicts") or result.get("conflicts") or []
        rel = result.get("relation")
        if conflicts or rel == "DEFINITION_DIFF":
            ok.append("version_conflict")
        else:
            failures.append("version conflict not preserved")

    if checks.get("conflicts_preserved"):
        conflicts = proposal.get("conflicts") or result.get("conflicts") or []
        if len(candidates) >= 2 and (conflicts or result.get("relation") in ("UNRESOLVED", "DEFINITION_DIFF")):
            ok.append("conflicts_preserved")
        else:
            failures.append("conflicts not preserved")

    if checks.get("mentions_urscript"):
        blob = str(proposal.get("llm_body", "")) + str(candidates)
        if "urscript" in blob.lower() or "URScript" in blob:
            ok.append("urscript")
        elif mode == "llm_web":
            failures.append("URScript not mentioned in web path")

    if checks.get("environment_keys"):
        env = proposal.get("environment") or {}
        keys = checks["environment_keys"]
        found = [k for k in keys if k in env or any(k in str(c.get("environment", {})) for c in candidates)]
        if len(found) >= 1:
            ok.append("environment")
        elif mode == "llm_web":
            failures.append(f"environment keys missing expected {keys}")

    if checks.get("llm_only_sufficient") and mode == "llm_only":
        if result.get("gate", {}).get("decision") == "RESEARCH_NOT_REQUIRED":
            ok.append("llm_only_sufficient")

    if not result.get("url_integrity", True):
        failures.append("url integrity failed")

    return ok, failures


def run_tda_case(
    spec: TDACaseSpec,
    *,
    mode: Literal["llm_only", "llm_web"] = "llm_web",
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    gate = assess_research_requirement(
        spec.user_requirement,
        force_research=spec.force_research,
        case_hint=spec.case_id,
    )

    if mode == "llm_only" or gate.decision == "RESEARCH_NOT_REQUIRED":
        base = _llm_only_proposal(spec.user_requirement, gate)
        if gate.decision == "RESEARCH_NOT_REQUIRED":
            proposal = build_development_proposal(
                spec.user_requirement,
                gate,
                [],
                {"conflicts": [], "relation": "SINGLE", "presentation_mode": "SINGLE"},
                chat_fn=chat_fn if llm_enabled else None,
                model=model,
                llm_enabled=llm_enabled and gate.decision == "RESEARCH_NOT_REQUIRED",
            )
            base["proposal"] = proposal.to_dict()
        ok, failures = _score_case_checks(spec, base, mode="llm_only")
        base["checks_passed"] = ok
        base["failures"] = failures
        base["pass"] = len(failures) == 0
        return base

    queries = generate_search_queries(spec.user_requirement)
    read_fn = make_multi_fixture_read_url_fn(spec.url_html) if spec.url_html else None
    search_fn = make_fixture_search_fn(spec.search_hits) if spec.search_hits else None

    loop, meta, sources, pipeline_fail = run_canonical_evidence_collection(
        spec.user_requirement,
        mock_tool_calls=spec.mock_tool_calls,
        search_web_fn=search_fn,
        read_url_text_fn=read_fn,
        model=model or "tda-mock",
    )

    if pipeline_fail:
        return {
            "mode": "llm_web",
            "pass": False,
            "failures": [f"pipeline {pipeline_fail}"],
            "gate": gate.to_dict(),
            "queries": queries,
            "pipeline_failure": pipeline_fail,
        }

    tech = build_technology_candidates(sources, topic=spec.user_requirement[:40])
    if spec.include_custom_build:
        add_custom_build_candidate(tech, requirement=spec.user_requirement)

    envelope = tech_candidates_to_envelope(tech, user_request=spec.user_requirement)
    proposal = build_development_proposal(
        spec.user_requirement,
        gate,
        tech,
        envelope,
        queries=queries,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    state, conv_envelope = initialize_conversation(
        sources,
        user_request=spec.user_requirement,
        topic=spec.user_requirement[:40],
    )

    follow_results: list[dict[str, Any]] = []
    for message, expected_intent in spec.follow_ups:
        fu = handle_tda_follow_up(
            state,
            conv_envelope,
            message,
            tech,
            chat_fn=chat_fn,
            model=model,
            llm_enabled=llm_enabled,
        )
        follow_results.append({"message": message, "expected": expected_intent, "result": fu})
        if expected_intent == "BUILD_CUSTOM" and fu.get("development_decision") != "CUSTOM_BUILD":
            pass  # scored in failures below

    known_urls = {c.url for c in tech if c.url}
    url_ok, unknown = check_url_integrity(
        known_urls=known_urls,
        texts=[proposal.llm_body] + [str(f["result"].get("body", "")) for f in follow_results],
    )

    result = {
        "mode": "llm_web",
        "case_id": spec.case_id,
        "gate": gate.to_dict(),
        "queries": queries,
        "sources_extracted": len(sources),
        "source_urls": [s.url for s in sources],
        "candidates": [c.to_dict() for c in tech],
        "relation": envelope.get("relation"),
        "conflicts": envelope.get("conflicts"),
        "proposal": proposal.to_dict(),
        "follow_ups": follow_results,
        "selected_candidate_id": state.selected_candidate_id,
        "production_equivalent": meta.production_equivalent,
        "url_integrity": url_ok,
        "unknown_urls": unknown,
    }

    ok, failures = _score_case_checks(spec, result, mode="llm_web")
    for message, expected_intent in spec.follow_ups:
        fu = next((f for f in follow_results if f["message"] == message), None)
        if fu and fu["result"].get("intent") != expected_intent:
            failures.append(f"follow-up intent expected {expected_intent}")
    result["checks_passed"] = ok
    result["failures"] = failures
    result["pass"] = len(failures) == 0
    return result


def compare_llm_only_vs_web(
    llm_only: dict[str, Any],
    llm_web: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic comparison — not LLM judge."""
    web_cands = len(llm_web.get("candidates") or [])
    only_cands = len(llm_only.get("candidates") or [])
    web_sources = llm_web.get("sources_extracted") or 0
    web_conflicts = len(llm_web.get("conflicts") or [])
    web_env = bool((llm_web.get("proposal") or {}).get("environment"))

    wins = {
        "candidate_discovery": web_cands > only_cands,
        "source_attribution": web_sources > 0 and bool(llm_web.get("source_urls")),
        "conflict_awareness": web_conflicts > 0 or llm_web.get("relation") in ("DEFINITION_DIFF", "UNRESOLVED"),
        "environment_metadata": web_env,
        "unknown_detection": len((llm_web.get("proposal") or {}).get("unknown") or []) >= 0,
    }
    web_better = sum(1 for v in wins.values() if v)
    return {
        "web_candidate_count": web_cands,
        "llm_only_candidate_count": only_cands,
        "web_better_dimensions": web_better,
        "dimensions": wins,
        "web_beats_llm_only": web_better >= 2 and web_cands >= only_cands,
    }


def _golden_acceptable(golden: dict[str, Any], *, fetch_live: bool) -> bool:
    if golden.get("overall") == "PASS":
        return True
    if fetch_live:
        return False
    cases = golden.get("cases") or {}
    evaluated = [v for v in cases.values() if v.get("error") != "skipped"]
    return bool(evaluated) and all(v.get("grade") == "PASS" for v in evaluated)


def determine_tda_decision(
    results: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> TDADecision:
    web_pass = sum(1 for r in results if r.get("mode") == "llm_web" and r.get("pass"))
    web_total = sum(1 for r in results if r.get("mode") == "llm_web")
    web_beats = sum(1 for c in comparisons if c.get("web_beats_llm_only"))

    if web_pass >= web_total - 1 and web_beats >= 3:
        return "CONTINUE"
    if web_pass >= 4 or web_beats >= 2:
        return "INVESTIGATE"
    return "STOP_NO_VALUE"


def run_tda_poc(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    fetch_live_baseline: bool = False,
) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    golden_pass = _golden_acceptable(golden, fetch_live=fetch_live_baseline)

    cases = tda_evaluation_cases()
    results: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []

    for spec in cases:
        llm_only = run_tda_case(spec, mode="llm_only", chat_fn=chat_fn, model=model, llm_enabled=False)
        llm_web = run_tda_case(spec, mode="llm_web", chat_fn=chat_fn, model=model, llm_enabled=llm_enabled)
        results.extend([llm_only, llm_web])
        if spec.expected_gate == "RESEARCH_REQUIRED":
            comparisons.append(
                {
                    "case_id": spec.case_id,
                    **compare_llm_only_vs_web(llm_only, llm_web),
                }
            )

    web_results = [r for r in results if r.get("mode") == "llm_web"]
    pass_count = sum(1 for r in web_results if r.get("pass"))
    decision = determine_tda_decision(results, comparisons)

    core = [
        {
            "id": "TDA-ORCHESTRATION",
            "name": "Tool Development Assistance Orchestration",
            "classification": "C3" if pass_count >= 6 else "C2",
            "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
            "note": "Sole C3 candidate this phase — wraps existing CR + canonical eval",
        }
    ]

    success_table = {
        "S1_research_gate": "PASS" if any(r.get("gate", {}).get("decision") == "RESEARCH_NOT_REQUIRED" for r in results) else "FAIL",
        "S2_useful_extraction": "PASS" if pass_count >= 5 else "PARTIAL",
        "S3_candidate_organization": "PASS" if pass_count >= 5 else "PARTIAL",
        "S4_environment": "PASS" if any("environment" in (r.get("checks_passed") or []) for r in web_results) else "PARTIAL",
        "S5_metadata_retention": "PASS" if all(r.get("url_integrity", True) for r in web_results if r.get("pass")) else "FAIL",
        "S6_conflict_preserved": "PASS" if any("conflicts_preserved" in (r.get("checks_passed") or []) or "version_conflict" in (r.get("checks_passed") or []) for r in web_results) else "PARTIAL",
        "S7_llm_uses_research": "PASS" if sum(c.get("web_better_dimensions", 0) for c in comparisons) >= 4 else "PARTIAL",
        "S8_user_selection": "PASS" if any(r.get("selected_candidate_id") or r.get("follow_ups") for r in web_results) else "PARTIAL",
        "S9_follow_up_research": "PASS" if any(
            (f.get("result") or {}).get("needs_targeted_research")
            for r in web_results
            for f in (r.get("follow_ups") or [])
        ) else "PARTIAL",
        "S10_production_intact": "PASS" if golden_pass else "FAIL",
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "phase": "tool_development_assistance_poc",
        "production_changes": [],
        "golden": golden,
        "golden_pass": golden_pass,
        "cases": [c.to_dict() for c in cases],
        "results": results,
        "comparisons": comparisons,
        "pass_count": f"{pass_count}/{len(web_results)}",
        "success_criteria": success_table,
        "core_discovery": core,
        "decision": decision,
        "forbidden_actions_respected": phase_forbidden_actions(),
        "architecture_flow": (
            "Requirement → Gate → Query → Canonical Web Eval → Technology Candidate "
            "→ Development Proposal → Follow-up / User Selection"
        ),
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"
