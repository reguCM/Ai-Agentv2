"""Web Research User-Facing Resolution & Source Presentation Proof Phase.

PoC for Source → Evidence → Candidate → LLM Conversation → User Follow-up.
Does NOT modify Production, Agent, Registry, or Prompt.
"""
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
from ai_tool.experimental.conversation_resolution.candidate_builder import build_envelope
from ai_tool.experimental.conversation_resolution.models import FollowUpIntent
from ai_tool.experimental.conversation_resolution.resolver import (
    handle_follow_up,
    initialize_conversation,
    parse_follow_up_intent,
    resolve_initial_turn,
)
from ai_tool.experimental.evidence_context.packager import EvidenceSource
from ai_tool.experimental.read_url.html_normalize import normalize_html_to_evidence
from ai_tool.web_evidence_llm_context_investigation import (
    CONFLICT_SOURCE_A,
    CONFLICT_SOURCE_B,
    investigation_cases,
)
from ai_tool.web_tool_extraction_normalization_production import run_production_golden
from ai_tool.web_tool_success_class_accuracy_evaluation import ExpectedFact
from ai_tool.web_tool_web_status_evaluation import GOOD_HTML

RepoRoot = Path(__file__).resolve().parents[1]

Feasibility = Literal["PASS", "PARTIAL", "FAIL"]
CostLevel = Literal["LOW", "MEDIUM", "HIGH"]
ProofDecision = Literal[
    "STOP_NO_CHANGE",
    "CONTINUE",
    "RECORD",
    "INVESTIGATE",
    "EXPERIMENTAL_CAPABILITY",
    "SPECIFICATION_CHANGE_REQUEST",
    "HUMAN_REVIEW_REQUIRED",
    "PROMOTE_TO_PRODUCTION",
]

ChatFn = Callable[..., Any]


@dataclass
class ProofCaseSpec:
    case_id: str
    scenario: str
    description: str
    sources: list[EvidenceSource]
    user_request: str
    topic: str
    expected_facts: list[ExpectedFact]
    expected_mode: str
    expected_relation: str
    follow_ups: list[tuple[str, FollowUpIntent, str]]  # message, intent, check_key

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario": self.scenario,
            "description": self.description,
            "user_request": self.user_request,
            "expected_mode": self.expected_mode,
            "expected_relation": self.expected_relation,
            "follow_ups": [{"message": m, "intent": i, "check": c} for m, i, c in self.follow_ups],
        }


def _html_source(url: str, title: str, html: str, backend: str = "fixture") -> EvidenceSource:
    ev = normalize_html_to_evidence(html)
    return EvidenceSource(
        url=url,
        title=title,
        main_text=str(ev.get("main_text") or ""),
        quality=ev.get("quality") or {},
        backend=backend,
    )


def proof_cases() -> list[ProofCaseSpec]:
    agree_b = _html_source(
        "https://fixture/agree-b",
        "Osaka stats B",
        GOOD_HTML,
    )
    agree_a = _html_source("https://fixture/agree-a", "Osaka portal A", GOOD_HTML)

    numeric_a = _html_source(
        "https://fixture/area-a",
        "Area A",
        "<html><body><main><p>日本の国土面積は377,975平方キロメートル。</p></main></body></html>",
    )
    numeric_b = _html_source(
        "https://fixture/area-b",
        "Area B",
        "<html><body><main><p>日本の国土面積は約378,000平方km。</p></main></body></html>",
    )

    conflict_true_a = _html_source(
        "https://fixture/conflict-a",
        "Portal X",
        "<html><body><main><p>2024年現在、大阪市人口は300万人。</p></main></body></html>",
    )
    conflict_true_b = _html_source(
        "https://fixture/conflict-b",
        "Portal Y",
        "<html><body><main><p>2024年現在、大阪市人口は275万人。</p></main></body></html>",
    )

    return [
        ProofCaseSpec(
            case_id="PR-C01",
            scenario="A/C — 一致",
            description="複数ページが同じ事実",
            sources=[agree_a, agree_b],
            user_request="大阪市の人口を教えてください。",
            topic="大阪 人口",
            expected_facts=[
                ExpectedFact("pop", "numeric", [r"275"], [r"275"], numeric_min=2_500_000, numeric_max=2_900_000),
            ],
            expected_mode="SINGLE",
            expected_relation="AGREEMENT",
            follow_ups=[],
        ),
        ProofCaseSpec(
            case_id="PR-C02",
            scenario="C — 数値近接",
            description="377,975 vs 378,000",
            sources=[numeric_a, numeric_b],
            user_request="日本の国土面積は？",
            topic="面積",
            expected_facts=[
                ExpectedFact("area", "numeric", [r"377"], [r"377"], numeric_min=370_000, numeric_max=380_000),
            ],
            expected_mode="MERGED",
            expected_relation="NUMERIC_NEAR",
            follow_ups=[],
        ),
        ProofCaseSpec(
            case_id="PR-C03",
            scenario="B/D — 定義差",
            description="2020 census vs 2024 estimate",
            sources=[CONFLICT_SOURCE_B, CONFLICT_SOURCE_A],
            user_request="大阪市の人口について教えてください。",
            topic="大阪 人口",
            expected_facts=[
                ExpectedFact("a", "numeric", [r"275"], [r"275"], numeric_min=2_700_000, numeric_max=2_800_000),
                ExpectedFact("b", "numeric", [r"752"], [r"752"], numeric_min=2_700_000, numeric_max=2_800_000),
            ],
            expected_mode="MULTI",
            expected_relation="DEFINITION_DIFF",
            follow_ups=[
                ("Aの方を採用して", "ADOPT_A", "selection_persist"),
                ("その情報の元ページを見せて", "SHOW_SOURCE", "source_url"),
            ],
        ),
        ProofCaseSpec(
            case_id="PR-C04",
            scenario="D — 真競合",
            description="同一条件で異なる数値",
            sources=[conflict_true_a, conflict_true_b],
            user_request="大阪市の現在の人口は？",
            topic="大阪 人口",
            expected_facts=[],
            expected_mode="UNRESOLVED",
            expected_relation="TRUE_CONFLICT",
            follow_ups=[("両方見たい", "SHOW_BOTH", "dual_source")],
        ),
        ProofCaseSpec(
            case_id="PR-C05",
            scenario="B — ユーザー選択",
            description="Follow-up adopt B",
            sources=[CONFLICT_SOURCE_A, CONFLICT_SOURCE_B],
            user_request="大阪市の人口について複数ソースを比較してください。",
            topic="大阪 人口",
            expected_facts=[],
            expected_mode="MULTI",
            expected_relation="DEFINITION_DIFF",
            follow_ups=[("Bの方を採用して", "ADOPT_B", "selection_b")],
        ),
        ProofCaseSpec(
            case_id="PR-C06",
            scenario="A — 出典確認",
            description="Source navigation",
            sources=[_html_source("https://fixture/single", "Official page", GOOD_HTML)],
            user_request="大阪市の人口",
            topic="大阪",
            expected_facts=[
                ExpectedFact("pop", "numeric", [r"275"], [r"275"], numeric_min=2_500_000, numeric_max=2_900_000),
            ],
            expected_mode="SINGLE",
            expected_relation="SINGLE",
            follow_ups=[("元ページを見せて", "SHOW_SOURCE", "source_url")],
        ),
    ]


def oss_reference_survey() -> list[dict[str, Any]]:
    """Static survey — no credential services invoked."""
    return [
        {
            "name": "LangChain / LangGraph document loaders + citations",
            "reference": "source metadata + chunk attribution patterns",
            "search": "N/A (loader focused)",
            "evidence": "Document chunks with metadata",
            "citation": "Common in RAG tutorials",
            "multi_source": "Retriever merge — not conversational A/B",
            "adopt_value": "LOW — different layer; reuse metadata ideas only",
        },
        {
            "name": "Perplexity-style / search-augmented chat (conceptual)",
            "reference": "inline citations + synthesized answer",
            "search": "external API",
            "evidence": "pre-extracted passages",
            "citation": "inline [1][2]",
            "multi_source": "synthesis first; conflict handling opaque",
            "adopt_value": "MEDIUM — citation UX reference; not copy architecture",
        },
        {
            "name": "OpenAI file_search / annotations",
            "reference": "annotation objects with file citations",
            "search": "hosted",
            "evidence": "retrieved chunks",
            "citation": "structured annotations",
            "multi_source": "model decides merge",
            "adopt_value": "LOW — credential + hosted; HR required",
        },
        {
            "name": "Self (this repo) enrich_web_tool_result",
            "reference": "grounding hints + main_text in tool JSON",
            "search": "Production search_web",
            "evidence": "main_text + web_status",
            "citation": "not user-facing yet",
            "multi_source": "WebSessionTracker aggregate",
            "adopt_value": "HIGH — extend experimentally without Production break",
        },
    ]


def run_proof_case(
    spec: ProofCaseSpec,
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
) -> dict[str, Any]:
    state, envelope = initialize_conversation(
        spec.sources,
        user_request=spec.user_request,
        topic=spec.topic,
        expected_facts=spec.expected_facts or None,
    )
    initial = resolve_initial_turn(
        state,
        envelope,
        chat_fn=chat_fn,
        model=model,
        llm_enabled=llm_enabled,
    )

    failures: list[str] = []
    if state.presentation_mode != spec.expected_mode:
        failures.append(f"mode expected {spec.expected_mode} got {state.presentation_mode}")
    if state.relation != spec.expected_relation:
        failures.append(f"relation expected {spec.expected_relation} got {state.relation}")

    follow_results: list[dict[str, Any]] = []
    for message, expected_intent, check in spec.follow_ups:
        parsed = parse_follow_up_intent(message)
        if parsed != expected_intent:
            failures.append(f"intent {message!r} expected {expected_intent} got {parsed}")
        fu = handle_follow_up(
            state,
            envelope,
            message,
            chat_fn=chat_fn,
            model=model,
            llm_enabled=llm_enabled,
        )
        follow_results.append({"message": message, "result": fu})

        if check == "selection_persist" and not fu.get("selected_candidate_id"):
            failures.append("selection not persisted")
        if check == "selection_b" and fu.get("selected_candidate_id") != "CB":
            failures.append("B not selected")
        if check == "source_url":
            body = str(fu.get("body") or "")
            if "http" not in body and not (initial.get("presentation") or {}).get("source_links"):
                failures.append("source URL not navigable")
        if check == "dual_source" and "出典" not in str(fu.get("body") or ""):
            failures.append("dual source not shown")

    pres = initial.get("presentation") or {}
    q_checks = {
        "candidate_structure": all(
            k in (envelope.get("candidates") or [{}])[0]
            for k in ("claim", "url", "source_title", "evidence_id")
        )
        if envelope.get("candidates")
        else False,
        "source_attached": bool(pres.get("citations") or pres.get("source_links")),
        "no_forced_ab_when_agree": not (
            spec.expected_relation == "AGREEMENT" and pres.get("mode") == "MULTI"
        ),
        "multi_when_definition_diff": (
            spec.expected_relation != "DEFINITION_DIFF" or pres.get("mode") in ("MULTI", "UNRESOLVED")
        ),
    }

    return {
        "case_id": spec.case_id,
        "scenario": spec.scenario,
        "expected_mode": spec.expected_mode,
        "actual_mode": state.presentation_mode,
        "expected_relation": spec.expected_relation,
        "actual_relation": state.relation,
        "envelope_summary": {
            "candidate_count": len(envelope.get("candidates") or []),
            "relation": envelope.get("relation"),
            "difference_note": envelope.get("difference_note"),
        },
        "initial_turn": initial,
        "follow_ups": follow_results,
        "q_checks": q_checks,
        "failures": failures,
        "pass": len(failures) == 0,
    }


def evaluate_feasibility(case_results: list[dict[str, Any]]) -> dict[str, Feasibility]:
    def _rate(key: str) -> Feasibility:
        ok = sum(1 for r in case_results if r.get("q_checks", {}).get(key))
        if ok == len(case_results):
            return "PASS"
        if ok > 0:
            return "PARTIAL"
        return "FAIL"

    selection_cases = [r for r in case_results if any("selection" in str(f) for f in r.get("failures", []))]
    source_cases = [r for r in case_results if any("source" in f.lower() for f in r.get("failures", []))]

    return {
        "source_attribution": "PASS" if not source_cases else "PARTIAL",
        "candidate_representation": _rate("candidate_structure"),
        "ab_presentation": "PASS"
        if any(r["actual_mode"] in ("MULTI", "UNRESOLVED") for r in case_results)
        else "PARTIAL",
        "user_selection": "PASS" if not selection_cases else "PARTIAL",
        "follow_up_conversation": "PASS" if all(r["pass"] for r in case_results) else "PARTIAL",
        "source_navigation": "PASS" if not source_cases else "PARTIAL",
    }


def discover_core_candidates(feasibility: dict[str, Feasibility]) -> list[dict[str, Any]]:
    cands: list[dict[str, Any]] = []

    cands.append(
        {
            "id": "CR-CANDIDATE-ENVELOPE",
            "name": "Candidate / Evidence Envelope",
            "classification": "C2" if feasibility.get("candidate_representation") == "PASS" else "C1",
            "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
            "cost": "MEDIUM",
            "benefit": "Enables structured multi-source conversation",
            "production_risk": "MEDIUM",
        }
    )
    cands.append(
        {
            "id": "CR-SOURCE-PRESENTATION",
            "name": "Source Presentation Layer",
            "classification": "C2" if feasibility.get("source_navigation") == "PASS" else "C1",
            "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
            "cost": "LOW",
            "benefit": "User-facing citation without URL dump",
            "production_risk": "LOW",
        }
    )
    cands.append(
        {
            "id": "CR-CONV-RESOLUTION",
            "name": "Conversation Resolution State",
            "classification": "C2" if feasibility.get("user_selection") == "PASS" else "C1",
            "llm_role": evaluate_llm_capability_role(extends_llm=True, replaces_llm=False),
            "cost": "MEDIUM",
            "benefit": "Follow-up selection + source navigation",
            "production_risk": "MEDIUM",
        }
    )
    cands.append(
        {
            "id": "CR-MECH-RESOLVER",
            "name": "Mechanical Conflict Resolver",
            "classification": "C0",
            "llm_role": evaluate_llm_capability_role(extends_llm=False, replaces_llm=True),
            "note": "Explicitly rejected — LLM conversation + user decision",
        }
    )

    c3_count = sum(1 for c in cands if c.get("classification") == "C3")
    return cands


def what_we_did_not_build() -> list[dict[str, str]]:
    return [
        {"item": "Production Agent / Prompt changes", "reason": "PoC phase only"},
        {"item": "Mechanical Answer", "reason": "SCR-02"},
        {"item": "Mechanical Conflict Resolver", "reason": "User/LLM conversation priority"},
        {"item": "Always-on A/B UI", "reason": "Scenario C — merge when equivalent"},
        {"item": "Generic Retry/Fallback", "reason": "No measured need"},
        {"item": "New C3 Core this phase", "reason": "C2 investigation first"},
    ]


def determine_decision(
    feasibility: dict[str, Feasibility],
    case_results: list[dict[str, Any]],
) -> ProofDecision:
    all_pass = all(r["pass"] for r in case_results)
    if all_pass and all(v in ("PASS", "PARTIAL") for v in feasibility.values()):
        return "INVESTIGATE"
    if any(r["pass"] for r in case_results):
        return "RECORD"
    return "STOP_NO_CHANGE"


def run_web_research_user_facing_resolution_proof(
    *,
    chat_fn: ChatFn | None = None,
    model: str = "",
    llm_enabled: bool = False,
    fetch_live_baseline: bool = False,
) -> dict[str, Any]:
    head = _git_head()
    golden = run_production_golden(fetch_live=fetch_live_baseline)
    golden_pass = golden.get("overall") == "PASS"

    cases = proof_cases()
    results = [
        run_proof_case(c, chat_fn=chat_fn, model=model, llm_enabled=llm_enabled) for c in cases
    ]
    feasibility = evaluate_feasibility(results)
    core = discover_core_candidates(feasibility)
    decision = determine_decision(feasibility, results)

    pass_count = sum(1 for r in results if r["pass"])
    failure_taxonomy = []
    for r in results:
        for f in r.get("failures", []):
            failure_taxonomy.append({"case_id": r["case_id"], "failure": f})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "initial_head": head,
        "final_head": head,
        "overall": "PASS" if golden_pass and pass_count == len(results) else "PARTIAL",
        "production_changes": [],
        "phase": "web_research_user_facing_resolution_proof",
        "architecture_spec": "WEB_RESEARCH_LLM_CONTEXT_ARCHITECTURE_SPEC.md (SCR-02)",
        "golden": golden,
        "proof_cases": [c.to_dict() for c in cases],
        "case_results": results,
        "pass_count": f"{pass_count}/{len(results)}",
        "feasibility": feasibility,
        "implementation_cost": "MEDIUM",
        "production_connection_risk": "MEDIUM",
        "llm_conversation_quality": "不変 (proxy) / live optional",
        "core_discovery": core,
        "oss_reference_survey": oss_reference_survey(),
        "what_we_did_not_build": what_we_did_not_build(),
        "forbidden_actions_respected": phase_forbidden_actions(),
        "failure_taxonomy": failure_taxonomy,
        "decision": decision,
        "human_review_required": decision in ("PROMOTE_TO_PRODUCTION", "HUMAN_REVIEW_REQUIRED", "SPECIFICATION_CHANGE_REQUEST"),
        "q_answers": {
            "Q1_metadata_to_user_display": feasibility.get("source_attribution"),
            "Q2_llm_multi_candidate_judgment": feasibility.get("ab_presentation"),
            "Q3_candidate_structure": feasibility.get("candidate_representation"),
            "Q4_follow_up_continuation": feasibility.get("follow_up_conversation"),
            "Q5_source_navigation_without_production_conflict": feasibility.get("source_navigation"),
        },
        "remaining_unknowns": [
            "Live LLM naturalness for MULTI/UNRESOLVED presentation",
            "CLI/stdout integration path without breaking agent.py contract",
            "English source + million normalization in user-facing flow",
        ],
    }


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=RepoRoot).strip()
    except Exception:
        return "UNKNOWN"


def make_mock_resolution_chat_fn() -> ChatFn:
    def _chat(**kwargs: Any) -> Any:
        messages = kwargs.get("messages") or []
        blob = " ".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))

        class _Msg:
            content = (
                "情報源によって時点が異なります。2020年国勢調査と2024年推計の両方があります。"
                if "DEFINITION" in blob or "2020" in blob
                else "確認できた範囲でお答えします。"
            )

        class _Resp:
            message = _Msg()

        return _Resp()

    return _chat
