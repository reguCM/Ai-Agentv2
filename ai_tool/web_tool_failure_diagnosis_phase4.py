"""Web Tool Failure Diagnosis Automation — Phase 4 (read-only diagnostic engine).

Deterministic rules first; no production changes; no auto-fix.
Generic taxonomy — not hardcoded to Search/Agent/LLM layer names as fixed concepts.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
KnowledgeType = Literal["CONFIRMED_FACT", "OBSERVATION", "HYPOTHESIS", "UNKNOWN"]
FailureClass = Literal[
    "TOOL_SELECTION",
    "TOOL_EXECUTION",
    "RESULT_QUALITY",
    "RESULT_UTILIZATION",
    "AGENT_POLICY",
    "PROMPT",
    "MODEL_CAPABILITY",
    "ENVIRONMENT",
    "REGISTRY",
    "INTERFACE",
    "SECURITY",
    "UNKNOWN",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE3_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_215543_web_tool_failure_isolation_phase3"
PHASE1_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_201538_web_tool_practical_evaluation"
PHASE2_RUN = REPO_ROOT / "runs" / "ai_tool" / "20260828_214841_web_tool_practical_evaluation_phase2"

MISSING = "MISSING_OBSERVATION"

FETCH_INTENT_MARKERS = ("読んで", "本文", "ページの内容", "fetch", "read_url")
HTML_META_MARKERS = ("HTML", "BeautifulSoup", "パーサー", "JSONデータ", "トリミング", "DOCTYPE")
UNCERTAINTY_MARKERS = ("確認でき", "提供できません", "不明", "わかりません", "見つかりません")
HALLUCINATION_NUMERIC = re.compile(r"(?:約|推計)?\s*[0-9]{1,3}[,，]?[0-9]{3,}\s*(?:万人|人)?")


@dataclass
class ObservationBundle:
    """Minimal observations required for failure diagnosis."""

    execution_id: str
    source: str
    test_case: str | None = None
    round_count: int | None = None
    tool_calls: dict[str, int] = field(default_factory=dict)
    tool_selection_trace: list[str] | None = None
    tool_execution_errors: list[str] = field(default_factory=list)
    agent_blocked: dict[str, bool | None] = field(default_factory=dict)
    user_request: str | None = None
    user_intent_markers: list[str] = field(default_factory=list)
    search_query: str | None = None
    search_hit_count: int | None = None
    search_top_title: str | None = None
    search_top_relevance_hint: str | None = None
    search_first_relevant: bool | None = None
    search_backend_has_relevant: bool | None = None
    search_backends_empty: list[str] = field(default_factory=list)
    search_all_backends_empty: bool | None = None
    search_expected_entity: str | None = None
    fetch_url: str | None = None
    fetch_ok: bool | None = None
    fetch_fact_ready: bool | None = None
    fetch_main_text_len: int | None = None
    fetch_warnings: list[str] = field(default_factory=list)
    final_answer: str | None = None
    answer_has_numeric_claim: bool | None = None
    answer_has_uncertainty: bool | None = None
    answer_html_meta: bool | None = None
    empty_search_in_trace: bool | None = None
    grounding_metadata: dict[str, Any] | None = None
    prompt_variant: str | None = None
    eval_harness_direct_execution: bool | None = None

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if self.tool_selection_trace is None:
            missing.append("tool_selection_trace")
        if self.agent_blocked.get("fetch") is None and self._needs_agent_blocked():
            missing.append("agent_blocked.fetch")
        if self.search_backend_has_relevant is None and self._needs_backend_relevance():
            missing.append("search_backend_has_relevant")
        return missing

    def _needs_agent_blocked(self) -> bool:
        return (self.tool_calls.get("read_url_text") or 0) == 0 and bool(self.user_intent_markers)

    def _needs_backend_relevance(self) -> bool:
        return self.search_hit_count is not None and self.search_hit_count > 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["missing_observations"] = self.missing_fields()
        return d


@dataclass
class CauseCandidate:
    cause: str
    classification: FailureClass
    confidence: Confidence
    reason: str


@dataclass
class Diagnosis:
    diagnosis_id: str
    symptom: str
    evidence: list[str]
    classification: FailureClass
    sub_classification: str
    confidence: Confidence
    confidence_reason: str
    knowledge_type: KnowledgeType
    eliminated_causes: list[dict[str, str]]
    remaining_causes: list[dict[str, str]]
    missing_observations: list[str]
    suggested_investigation: list[str]
    deterministic: bool
    llm_assisted: bool = False
    observation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementProposal:
    option_id: str
    diagnosis_id: str
    target: str
    expected_benefit: str
    risk: str
    compatibility: str
    implementation_scope: str
    regression_risk: str
    automation_suitability: str
    remaining_unknowns: str
    human_review_required: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_fetch_intent(text: str) -> bool:
    return any(m in text for m in FETCH_INTENT_MARKERS)


def _detect_intent_markers(text: str) -> list[str]:
    return [m for m in FETCH_INTENT_MARKERS if m in text]


def _has_html_meta(answer: str | None) -> bool:
    if not answer:
        return False
    return any(m in answer for m in HTML_META_MARKERS)


def _has_uncertainty(answer: str | None) -> bool:
    if not answer:
        return False
    return any(m in answer for m in UNCERTAINTY_MARKERS)


def _has_numeric_claim(answer: str | None) -> bool:
    if not answer:
        return False
    return bool(HALLUCINATION_NUMERIC.search(answer))


def _backend_has_entity(per_backend: dict[str, list], entity: str | None) -> bool | None:
    if not entity:
        return None
    for hits in per_backend.values():
        for h in hits:
            if entity in str(h.get("title") or ""):
                return True
    return False


def observation_from_live_trace(case: dict[str, Any], *, source: str) -> ObservationBundle:
    tools = case.get("selected_tools") or []
    tool_calls: dict[str, int] = {}
    for t in tools:
        tool_calls[t] = tool_calls.get(t, 0) + 1

    user_request = str(case.get("user_request") or "")
    tool_results = case.get("tool_results") or []
    search_hits: list[dict] = []
    empty_search = False
    for r in tool_results:
        if isinstance(r, dict) and "hits" in r:
            hits = r.get("hits") or []
            if not hits:
                empty_search = True
            if hits and not search_hits:
                search_hits = hits

    top = search_hits[0] if search_hits else {}
    final = case.get("final_answer")
    fetch_results = [r for r in tool_results if isinstance(r, dict) and "main_text" in r]
    fetch_r = fetch_results[-1] if fetch_results else {}
    quality = fetch_r.get("quality") if isinstance(fetch_r, dict) else {}

    return ObservationBundle(
        execution_id=f"{source}:{case.get('case_id', 'unknown')}",
        source=source,
        test_case=str(case.get("case_id") or ""),
        round_count=int(case.get("tool_call_count") or 0),
        tool_calls=tool_calls,
        tool_selection_trace=list(tools) if tools else [],
        tool_execution_errors=[str(e) for e in (case.get("execution_errors") or [])],
        agent_blocked={"fetch": False},
        user_request=user_request,
        user_intent_markers=_detect_intent_markers(user_request),
        search_query=(case.get("tool_arguments") or [{}])[0].get("query") if case.get("tool_arguments") else None,
        search_hit_count=len(search_hits),
        search_top_title=str(top.get("title") or "") or None,
        search_top_relevance_hint=str(top.get("relevance_hint") or "") or None,
        search_first_relevant=None,
        search_backend_has_relevant=None,
        search_backends_empty=[],
        search_all_backends_empty=empty_search and not search_hits,
        search_expected_entity=None,
        fetch_url=str((case.get("tool_arguments") or [{}])[-1].get("url") or "") or None,
        fetch_ok=fetch_r.get("ok") if fetch_r else None,
        fetch_fact_ready=(quality or {}).get("fact_ready") if isinstance(quality, dict) else None,
        fetch_main_text_len=len(str(fetch_r.get("main_text") or "")) if fetch_r else None,
        fetch_warnings=list((quality or {}).get("warnings") or []) if isinstance(quality, dict) else [],
        final_answer=str(final) if final is not None else None,
        answer_has_numeric_claim=_has_numeric_claim(str(final) if final else None),
        answer_has_uncertainty=_has_uncertainty(str(final) if final else None),
        answer_html_meta=_has_html_meta(str(final) if final else None),
        empty_search_in_trace=empty_search,
        grounding_metadata=(tool_results[0].get("grounding") if tool_results and isinstance(tool_results[0], dict) else None),
        prompt_variant=str(case.get("prompt_variant") or case.get("mode") or ""),
        eval_harness_direct_execution=True,
    )


def observation_from_search_row(row: dict[str, Any]) -> ObservationBundle:
    hits = row.get("post_rank_hits") or []
    top = hits[0] if hits else {}
    per_backend = row.get("per_backend") or {}
    entity = row.get("expected_entity")
    backends_empty = [k for k, v in per_backend.items() if not v]
    all_empty = not hits and not any(per_backend.values())

    return ObservationBundle(
        execution_id=f"search_probe:{row.get('label', row.get('query'))}",
        source="search_isolation_probe",
        test_case=str(row.get("label") or ""),
        tool_calls={"search_web": 1},
        tool_selection_trace=["search_web"],
        search_query=str(row.get("query") or ""),
        search_hit_count=len(hits),
        search_top_title=str(top.get("title") or "") or None,
        search_top_relevance_hint=str(top.get("relevance_hint") or "") or None,
        search_first_relevant=row.get("first_hit_relevant"),
        search_backend_has_relevant=_backend_has_entity(per_backend, entity),
        search_backends_empty=backends_empty,
        search_all_backends_empty=all_empty,
        search_expected_entity=entity,
        eval_harness_direct_execution=True,
    )


def observation_from_fetch_probe(probe: dict[str, Any]) -> ObservationBundle:
    return ObservationBundle(
        execution_id=f"fetch_probe:{probe.get('url', 'unknown')[:48]}",
        source="fetch_isolation_probe",
        test_case="fetch_quality",
        tool_calls={"read_url_text": 1},
        tool_selection_trace=["read_url_text"],
        fetch_url=str(probe.get("url") or ""),
        fetch_ok=probe.get("ok"),
        fetch_fact_ready=probe.get("fact_ready"),
        fetch_main_text_len=int(probe.get("main_text_len") or 0),
        fetch_warnings=list(probe.get("warnings") or []),
        eval_harness_direct_execution=True,
    )


RuleFn = Callable[[ObservationBundle], Diagnosis | None]


def _eliminated(name: str, reason: str) -> dict[str, str]:
    return {"cause": name, "reason": reason}


def _remaining(name: str, classification: FailureClass, confidence: Confidence, reason: str) -> dict[str, str]:
    return {"cause": name, "classification": classification, "confidence": confidence, "reason": reason}


def rule_fetch_not_executed(obs: ObservationBundle) -> Diagnosis | None:
    fetch_calls = obs.tool_calls.get("read_url_text") or 0
    search_calls = obs.tool_calls.get("search_web") or 0
    if not obs.user_intent_markers or fetch_calls > 0:
        return None
    if search_calls == 0:
        return None

    eliminated: list[dict[str, str]] = []
    remaining: list[dict[str, str]] = []
    missing = obs.missing_fields()
    confidence: Confidence = "UNKNOWN"
    knowledge: KnowledgeType = "OBSERVATION"
    sub = "fetch_not_selected"
    classification: FailureClass = "UNKNOWN"

    if obs.agent_blocked.get("fetch") is True:
        eliminated.append(_eliminated("LLM did not select fetch", "agent_blocked_fetch=true"))
        remaining.append(_remaining("Agent policy blocked fetch", "AGENT_POLICY", "HIGH", "agent_blocked=true"))
        classification = "AGENT_POLICY"
        confidence = "HIGH"
        knowledge = "CONFIRMED_FACT"
    elif obs.agent_blocked.get("fetch") is False:
        eliminated.append(_eliminated("Agent blocked fetch", "agent_blocked_fetch=false"))

    if obs.tool_execution_errors:
        remaining.append(_remaining("Fetch execution failure", "TOOL_EXECUTION", "MEDIUM", "execution errors present"))
    else:
        eliminated.append(_eliminated("Fetch tool execution failure", "no fetch execution errors observed"))

    if obs.tool_selection_trace is not None:
        if "read_url_text" not in obs.tool_selection_trace:
            remaining.append(
                _remaining(
                    "Tool selector did not choose fetch tool",
                    "TOOL_SELECTION",
                    "HIGH",
                    "explicit fetch intent + fetch_calls=0 + trace lacks read_url_text",
                )
            )
            classification = "TOOL_SELECTION"
            confidence = "HIGH"
            knowledge = "CONFIRMED_FACT"
        else:
            eliminated.append(_eliminated("LLM did not select fetch", "read_url_text appears in selection trace"))
            remaining.append(_remaining("Fetch selected but not executed", "TOOL_EXECUTION", "MEDIUM", "trace mismatch"))
            classification = "TOOL_EXECUTION"
            confidence = "MEDIUM"
    else:
        missing.append("tool_selection_trace")
        remaining.append(
            _remaining(
                "Tool selector did not choose fetch tool",
                "TOOL_SELECTION",
                "UNKNOWN",
                "fetch_calls=0 but selection trace missing",
            )
        )
        if classification == "UNKNOWN":
            classification = "TOOL_SELECTION"

    if obs.prompt_variant and "minimal" in obs.prompt_variant:
        remaining.append(
            _remaining("Prompt insufficient for fetch selection", "PROMPT", "MEDIUM", "minimal prompt variant observed")
        )

    return Diagnosis(
        diagnosis_id="fetch_not_executed",
        symptom="fetch_not_called",
        evidence=[
            "user_explicit_fetch_request",
            f"fetch_calls={fetch_calls}",
            f"agent_blocked_fetch={obs.agent_blocked.get('fetch')}",
            f"search_calls={search_calls}",
        ],
        classification=classification,
        sub_classification=sub,
        confidence=confidence,
        confidence_reason=(
            "Multiple independent observations support tool selection failure"
            if confidence == "HIGH"
            else "Selection trace missing or alternative causes not fully eliminated"
        ),
        knowledge_type=knowledge,
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=missing,
        suggested_investigation=[
            "deterministic fixed-search-result test with explicit fetch instruction",
            "compare detailed vs minimal prompt on same trace fixture",
        ],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_wrong_search_result(obs: ObservationBundle) -> Diagnosis | None:
    if obs.search_hit_count is None or obs.search_hit_count == 0:
        return None
    if obs.search_first_relevant is not False and obs.search_top_relevance_hint not in ("low",):
        if obs.search_first_relevant is True:
            return None
        if obs.search_top_relevance_hint not in ("low",):
            return None

    eliminated: list[dict[str, str]] = []
    remaining: list[dict[str, str]] = []
    missing = obs.missing_fields()
    confidence: Confidence = "MEDIUM"
    classification: FailureClass = "RESULT_QUALITY"
    sub = "irrelevant_top_hit"

    if obs.search_backend_has_relevant is True:
        eliminated.append(_eliminated("Backend coverage gap", "raw backend contains relevant page"))
        remaining.append(
            _remaining("Ranking or query shaping", "RESULT_QUALITY", "HIGH", "relevant page exists but not ranked first")
        )
        confidence = "HIGH"
        sub = "ranking_or_query_shaping"
    elif obs.search_backend_has_relevant is False:
        eliminated.append(_eliminated("Ranking only", "backend lacks relevant entity entirely"))
        remaining.append(_remaining("Query generation or backend coverage", "ENVIRONMENT", "MEDIUM", "no relevant raw hit"))
        classification = "ENVIRONMENT"
    else:
        missing.append("search_backend_has_relevant")
        remaining.append(_remaining("Ranking vs backend vs query", "RESULT_QUALITY", "UNKNOWN", "backend relevance unknown"))

    if obs.search_query and "の" in obs.search_query:
        remaining.append(
            _remaining("Query variant generation", "MODEL_CAPABILITY", "MEDIUM", "の-insertion query pattern observed")
        )

    return Diagnosis(
        diagnosis_id="wrong_search_result",
        symptom="wrong_search_top_result",
        evidence=[
            f"query={obs.search_query}",
            f"top_title={obs.search_top_title}",
            f"first_hit_relevant={obs.search_first_relevant}",
            f"backend_has_relevant={obs.search_backend_has_relevant}",
        ],
        classification=classification,
        sub_classification=sub,
        confidence=confidence,
        confidence_reason="Backend raw vs ranked first divergence" if confidence == "HIGH" else "Partial backend data",
        knowledge_type="CONFIRMED_FACT" if confidence == "HIGH" else "HYPOTHESIS",
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=missing,
        suggested_investigation=[
            "run query variant matrix (space vs の-insertion) on same entity",
            "capture per_backend titles before ranking",
        ],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_empty_search(obs: ObservationBundle) -> Diagnosis | None:
    if not obs.search_all_backends_empty and obs.search_hit_count != 0:
        if obs.empty_search_in_trace is not True:
            return None
    if obs.search_hit_count and obs.search_hit_count > 0:
        return None

    eliminated = [_eliminated("Fetch quality", "no fetch occurred or search empty first")]
    remaining = [
        _remaining("Backend returned no hits", "ENVIRONMENT", "HIGH", "all backends empty or zero hits"),
        _remaining("Query no match", "MODEL_CAPABILITY", "MEDIUM", "query may not match index prefix"),
    ]
    return Diagnosis(
        diagnosis_id="empty_search",
        symptom="empty_search",
        evidence=[
            f"search_hit_count={obs.search_hit_count}",
            f"backends_empty={obs.search_backends_empty}",
            f"all_backends_empty={obs.search_all_backends_empty}",
        ],
        classification="ENVIRONMENT",
        sub_classification="no_hits",
        confidence="HIGH" if obs.search_all_backends_empty else "MEDIUM",
        confidence_reason="Zero hits observed across trace or probe",
        knowledge_type="CONFIRMED_FACT",
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=obs.missing_fields(),
        suggested_investigation=["retry with simplified query", "per-backend isolation probe"],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_hallucinated_number(obs: ObservationBundle) -> Diagnosis | None:
    if not obs.answer_has_numeric_claim:
        return None
    if not obs.empty_search_in_trace and obs.search_hit_count not in (0, None):
        return None
    if obs.answer_has_uncertainty:
        return None

    eliminated = []
    if obs.agent_blocked.get("fetch") is False:
        eliminated.append(_eliminated("Agent blocked answer", "no agent block observed"))
    if (obs.tool_calls.get("read_url_text") or 0) == 0:
        eliminated.append(_eliminated("Fetch extraction quality", "fetch not executed"))

    remaining = [
        _remaining("Model grounded answer failure", "MODEL_CAPABILITY", "HIGH", "numeric claim without uncertainty after empty search"),
        _remaining("Agent grounding enforcement absent", "AGENT_POLICY", "MEDIUM", "eval harness direct execution"),
        _remaining("Prompt grounding contract insufficient", "PROMPT", "MEDIUM", "minimal/detailed prompt did not prevent numeric fill"),
    ]
    return Diagnosis(
        diagnosis_id="hallucinated_number",
        symptom="hallucinated_numeric_answer",
        evidence=[
            "empty_search_in_trace",
            "answer_has_numeric_claim=true",
            "answer_has_uncertainty=false",
        ],
        classification="MODEL_CAPABILITY",
        sub_classification="numeric_without_evidence",
        confidence="MEDIUM",
        confidence_reason="Empty search + numeric answer; Agent/Prompt contribution not fully isolated",
        knowledge_type="HYPOTHESIS",
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=obs.missing_fields(),
        suggested_investigation=["production agent loop test with grounding enforce", "fixed empty-search trace replay"],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_fact_ready_false(obs: ObservationBundle) -> Diagnosis | None:
    if obs.fetch_ok is not True:
        return None
    if obs.fetch_fact_ready is not False:
        return None

    eliminated = [
        _eliminated("Fetch not executed", "fetch_ok=true"),
        _eliminated("HTTP failure", "fetch succeeded"),
    ]
    remaining = [
        _remaining("Extraction / main_text quality", "RESULT_QUALITY", "HIGH", "fact_ready=false after successful fetch"),
    ]
    if obs.fetch_warnings:
        remaining.append(
            _remaining("Boilerplate or metadata in main_text", "RESULT_QUALITY", "MEDIUM", f"warnings={obs.fetch_warnings}")
        )

    return Diagnosis(
        diagnosis_id="fact_ready_false",
        symptom="fetch_fact_ready_false",
        evidence=[
            "fetch_ok=true",
            "fact_ready=false",
            f"main_text_len={obs.fetch_main_text_len}",
            f"warnings={obs.fetch_warnings}",
        ],
        classification="RESULT_QUALITY",
        sub_classification="evidence_not_fact_ready",
        confidence="HIGH",
        confidence_reason="Fetch executed successfully; quality gate rejected evidence",
        knowledge_type="CONFIRMED_FACT",
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=obs.missing_fields(),
        suggested_investigation=["HTML fixture tests for target URL", "compare main_text sample against expected fact patterns"],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_html_meta_response(obs: ObservationBundle) -> Diagnosis | None:
    if not obs.answer_html_meta:
        return None
    eliminated = []
    if (obs.tool_calls.get("read_url_text") or 0) > 0:
        eliminated.append(_eliminated("Fetch not executed", "fetch was called"))
    remaining = [
        _remaining("Result utilization — answered about HTML not content", "RESULT_UTILIZATION", "HIGH", "meta markers in final answer"),
        _remaining("Evidence pipeline not applied", "RESULT_QUALITY", "MEDIUM", "pre-pipeline raw content in answer"),
    ]
    return Diagnosis(
        diagnosis_id="html_meta_response",
        symptom="html_meta_in_answer",
        evidence=["answer_html_meta=true", f"fetch_calls={obs.tool_calls.get('read_url_text', 0)}"],
        classification="RESULT_UTILIZATION",
        sub_classification="meta_instead_of_content",
        confidence="HIGH",
        confidence_reason="Answer contains HTML/parser meta markers",
        knowledge_type="CONFIRMED_FACT",
        eliminated_causes=eliminated,
        remaining_causes=remaining,
        missing_observations=obs.missing_fields(),
        suggested_investigation=["verify evidence pipeline on same URL post-fix baseline"],
        deterministic=True,
        observation_id=obs.execution_id,
    )


def rule_backend_failure(obs: ObservationBundle) -> Diagnosis | None:
    if obs.source != "search_isolation_probe":
        return None
    if not obs.search_backends_empty:
        return None
    if obs.search_hit_count and obs.search_hit_count > 0:
        return None

    return Diagnosis(
        diagnosis_id="backend_failure",
        symptom="search_backend_empty",
        evidence=[f"backends_empty={obs.search_backends_empty}", f"query={obs.search_query}"],
        classification="ENVIRONMENT",
        sub_classification="backend_coverage_gap",
        confidence="HIGH",
        confidence_reason="Named backend returned zero hits while probe executed",
        knowledge_type="CONFIRMED_FACT",
        eliminated_causes=[_eliminated("Ranking", "no hits to rank")],
        remaining_causes=[
            _remaining("Backend API/network failure", "ENVIRONMENT", "MEDIUM", "backend returned empty"),
            _remaining("Query-backend mismatch", "RESULT_QUALITY", "MEDIUM", "query not matched by backend index"),
        ],
        missing_observations=obs.missing_fields(),
        suggested_investigation=["backend-specific retry", "capture HTTP error if any"],
        deterministic=True,
        observation_id=obs.execution_id,
    )


DIAGNOSTIC_RULES: list[RuleFn] = [
    rule_fetch_not_executed,
    rule_wrong_search_result,
    rule_empty_search,
    rule_hallucinated_number,
    rule_fact_ready_false,
    rule_html_meta_response,
    rule_backend_failure,
]


def diagnose(obs: ObservationBundle, *, rules: list[RuleFn] | None = None) -> list[Diagnosis]:
    """Run deterministic rules; same input → same diagnoses."""
    out: list[Diagnosis] = []
    seen: set[str] = set()
    for rule in rules or DIAGNOSTIC_RULES:
        d = rule(obs)
        if d and d.diagnosis_id not in seen:
            out.append(d)
            seen.add(d.diagnosis_id)
    return out


def llm_assisted_refine(diagnoses: list[Diagnosis], obs: ObservationBundle) -> list[Diagnosis]:
    """Design stub — Phase 4 does not invoke LLM. Marks boundary for future use."""
    return diagnoses


PROPOSAL_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "fetch_not_executed": [
        {
            "option_id": "A",
            "target": "agent_policy",
            "expected_benefit": "Fetch gate after search when user intent requires reading",
            "risk": "Over-fetch on low-quality hits",
            "compatibility": "Requires agent loop change — Human Review",
            "implementation_scope": "SMALL-MEDIUM",
            "regression_risk": "MEDIUM",
            "automation_suitability": "MEDIUM — needs production agent tests",
            "remaining_unknowns": "Gate conditions without SSRF risk",
        },
        {
            "option_id": "B",
            "target": "prompt_contract",
            "expected_benefit": "Raise fetch selection rate via contract hints",
            "risk": "Does not guarantee utilization",
            "compatibility": "Prompt-only — Human Review",
            "implementation_scope": "SMALL",
            "regression_risk": "LOW",
            "automation_suitability": "HIGH — A/B on fixed traces",
            "remaining_unknowns": "Minimal vs detailed optimal wording",
        },
        {
            "option_id": "C",
            "target": "tool_selection_policy",
            "expected_benefit": "Post-search tool recommendation metadata",
            "risk": "Interface/metadata expansion",
            "compatibility": "Registry/tool result shape — Human Review",
            "implementation_scope": "MEDIUM",
            "regression_risk": "LOW-MEDIUM",
            "automation_suitability": "HIGH",
            "remaining_unknowns": "Whether metadata alone changes LLM behavior",
        },
    ],
    "wrong_search_result": [
        {
            "option_id": "A",
            "target": "result_quality_ranking",
            "expected_benefit": "Correct irrelevant first hit when backend has entity",
            "risk": "Site-specific overfitting",
            "compatibility": "Search tool — Human Review",
            "implementation_scope": "MEDIUM",
            "regression_risk": "MEDIUM",
            "automation_suitability": "HIGH — probe matrix",
            "remaining_unknowns": "Query variant interaction",
        },
        {
            "option_id": "B",
            "target": "model_capability_query_generation",
            "expected_benefit": "Steer LLM toward space-variant queries",
            "risk": "Prompt-only partial fix",
            "compatibility": "Prompt — Human Review",
            "implementation_scope": "SMALL",
            "regression_risk": "LOW",
            "automation_suitability": "MEDIUM",
            "remaining_unknowns": "Generalization beyond Japanese の-pattern",
        },
    ],
    "hallucinated_number": [
        {
            "option_id": "A",
            "target": "agent_policy_grounding",
            "expected_benefit": "Block numeric claims when empty_search",
            "risk": "False negatives on legitimate inference",
            "compatibility": "Agent — Human Review",
            "implementation_scope": "SMALL-MEDIUM",
            "regression_risk": "MEDIUM",
            "automation_suitability": "MEDIUM",
            "remaining_unknowns": "Production vs eval path parity",
        },
    ],
    "fact_ready_false": [
        {
            "option_id": "A",
            "target": "result_quality_extraction",
            "expected_benefit": "Improve main_text and fact_ready for target pages",
            "risk": "Maintenance per site template",
            "compatibility": "Fetch/read_url — Human Review",
            "implementation_scope": "MEDIUM",
            "regression_risk": "LOW-MEDIUM",
            "automation_suitability": "HIGH — HTML fixtures",
            "remaining_unknowns": "JS-rendered pages",
        },
    ],
}


def generate_proposals(diagnoses: list[Diagnosis]) -> list[ImprovementProposal]:
    proposals: list[ImprovementProposal] = []
    for d in diagnoses:
        templates = PROPOSAL_TEMPLATES.get(d.diagnosis_id, [])
        for t in templates:
            proposals.append(
                ImprovementProposal(
                    option_id=f"{d.diagnosis_id}_{t['option_id']}",
                    diagnosis_id=d.diagnosis_id,
                    target=t["target"],
                    expected_benefit=t["expected_benefit"],
                    risk=t["risk"],
                    compatibility=t["compatibility"],
                    implementation_scope=t["implementation_scope"],
                    regression_risk=t["regression_risk"],
                    automation_suitability=t["automation_suitability"],
                    remaining_unknowns=t["remaining_unknowns"],
                    human_review_required=True,
                )
            )
    return proposals


def build_human_review_packet(diagnoses: list[Diagnosis], proposals: list[ImprovementProposal]) -> dict[str, Any]:
    return {
        "stage": "Human Review",
        "production_changes_allowed": False,
        "diagnosis_count": len(diagnoses),
        "proposal_count": len(proposals),
        "all_proposals_require_human_review": all(p.human_review_required for p in proposals),
        "workflow": [
            "Failure",
            "Observation",
            "Diagnosis",
            "Proposal",
            "Risk assessment",
            "Human Review",
            "Approved Implementation (future phase)",
        ],
        "diagnoses": [d.to_dict() for d in diagnoses],
        "proposals": [p.to_dict() for p in proposals],
    }


def load_phase3_inputs() -> dict[str, Any]:
    analysis_path = PHASE3_RUN / "analysis.json"
    if analysis_path.is_file():
        return json.loads(analysis_path.read_text(encoding="utf-8"))
    return {}


def load_live_traces() -> list[ObservationBundle]:
    obs_list: list[ObservationBundle] = []
    for run_dir, label in ((PHASE1_RUN, "phase1_detailed"), (PHASE2_RUN, "phase2_minimal")):
        if not run_dir.is_dir():
            continue
        for path in sorted(run_dir.glob("case_*_live*.json")):
            case = json.loads(path.read_text(encoding="utf-8"))
            obs_list.append(observation_from_live_trace(case, source=f"{label}:{run_dir.name}"))
    return obs_list


def run_failure_diagnosis() -> dict[str, Any]:
    phase3 = load_phase3_inputs()
    observations: list[ObservationBundle] = load_live_traces()

    for row in phase3.get("search_isolation") or []:
        observations.append(observation_from_search_row(row))
    for probe in phase3.get("fetch_isolation") or []:
        observations.append(observation_from_fetch_probe(probe))

    all_diagnoses: list[Diagnosis] = []
    by_obs: dict[str, list[Diagnosis]] = {}
    for obs in observations:
        dx = diagnose(obs)
        dx = llm_assisted_refine(dx, obs)
        by_obs[obs.execution_id] = dx
        all_diagnoses.extend(dx)

    proposals = generate_proposals(all_diagnoses)
    review_packet = build_human_review_packet(all_diagnoses, proposals)

    failure_case_summary = summarize_failure_cases(all_diagnoses, observations)

    return {
        "observations": [o.to_dict() for o in observations],
        "diagnoses_by_observation": {k: [d.to_dict() for d in v] for k, v in by_obs.items()},
        "diagnoses": [d.to_dict() for d in all_diagnoses],
        "proposals": [p.to_dict() for p in proposals],
        "human_review_packet": review_packet,
        "failure_case_summary": failure_case_summary,
        "engine_metadata": {
            "deterministic_rules": len(DIAGNOSTIC_RULES),
            "llm_assisted_in_phase4": False,
            "taxonomy": [
                "TOOL_SELECTION",
                "TOOL_EXECUTION",
                "RESULT_QUALITY",
                "RESULT_UTILIZATION",
                "AGENT_POLICY",
                "PROMPT",
                "MODEL_CAPABILITY",
                "ENVIRONMENT",
                "REGISTRY",
                "INTERFACE",
                "SECURITY",
                "UNKNOWN",
            ],
        },
        "generalization_assessment": assess_generalization(),
        "boundary_design": boundary_design(),
    }


def summarize_failure_cases(diagnoses: list[Diagnosis], observations: list[ObservationBundle]) -> dict[str, Any]:
    ids = {d.diagnosis_id for d in diagnoses}
    cases = {
        "fetch_not_executed": "fetch_not_executed" in ids,
        "wrong_search_result": "wrong_search_result" in ids,
        "empty_search": "empty_search" in ids,
        "hallucinated_number": "hallucinated_number" in ids,
        "fact_ready_false": "fact_ready_false" in ids,
        "html_meta_response": "html_meta_response" in ids,
        "backend_failure": "backend_failure" in ids,
    }
    return {
        "cases_detected": cases,
        "observation_count": len(observations),
        "diagnosis_count": len(diagnoses),
        "all_seven_targets": all(
            cases[k]
            for k in (
                "fetch_not_executed",
                "wrong_search_result",
                "empty_search",
                "hallucinated_number",
                "fact_ready_false",
                "html_meta_response",
                "backend_failure",
            )
        ),
    }


def assess_generalization() -> dict[str, str]:
    return {
        "observation_tool": "Applicable — same ObservationBundle + TOOL_EXECUTION/RESULT_QUALITY rules",
        "tool_calling": "Applicable — tool_selection_trace + TOOL_SELECTION rules",
        "registry": "Partial — missing tool schema observations; extend with REGISTRY class",
        "safety_check": "Partial — SECURITY class reserved; needs policy violation observations",
        "self_repair": "Not in scope — diagnosis output feeds future implementation phase only",
    }


def boundary_design() -> dict[str, Any]:
    return {
        "deterministic": [
            "fetch_calls=0 with explicit intent and selection trace",
            "fetch_ok + fact_ready=false",
            "empty search hit count",
            "answer_html_meta markers",
            "backend empty list from probe",
        ],
        "llm_assisted_future": [
            "disambiguate multiple remaining causes with similar confidence",
            "compare complex multi-step traces",
            "natural language symptom clustering",
        ],
        "human_required": [
            "any production tool/agent/prompt/registry change approval",
            "security policy changes",
            "confidence HIGH but impact HIGH proposals",
        ],
    }


def engine_status(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("failure_case_summary") or {}
    return {
        "status": "PASS" if summary.get("all_seven_targets") else "PARTIAL",
        "deterministic": True,
        "llm_assisted": False,
        "rule_count": (result.get("engine_metadata") or {}).get("deterministic_rules", 0),
    }
