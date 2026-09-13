"""Grill-me style interview loop for E2E and observation harnesses.

Implements a bounded subset of `.agents/skills/grill-me/SKILL.md`:
- one question per round with a recommended answer
- auto-select recommended answers (temporary test default)
- five-dimension ambiguity scoring and aggregate gate
- aligned numbered spec for downstream Production Chat
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ai_tool.grill_question_contract import (
    GRILL_REASON_INITIAL,
    SELECTION_POLICY_TEST_AUTO,
    apply_selection_policy,
    normalize_grill_question_payload,
)
from ai_tool.llm_json_parse import (
    LLMEmptyResponseError,
    llm_response_diagnostics,
    message_content,
    parse_json_content,
    strip_json_fence,
)
from ai_tool.pipeline_observations import PipelineObserver, observed_llm_json
from tools.system.llm import chat as llm_chat

LLM_JSON_MAX_ATTEMPTS = 3

PHASE1_GRILL = "phase1_grill"


DIMENSIONS = ("goals", "acceptance", "boundaries", "alternatives", "assumptions")
TEST_AUTO_RECOMMENDATION_POLICY = "test_auto_recommendation"
SIMULATED_HUMAN_RESPONSE_KIND = "simulated_human"
THRESHOLDS = {
    "freeform": 0.4,
    "spec": 0.2,
    "ticket": 0.3,
}

TETRIS_VAGUE_REQUEST = "テトリスを作って"

TETRIS_FALLBACK_SPEC: dict[str, Any] = {
    "title": "Dedicated Sandbox 最小テトリス",
    "summary": (
        "Dedicated Sandbox 内に Python コンソール版の最小テトリスを1ファイルで作成する。"
    ),
    "numbered_conditions": [
        "Dedicated Sandbox 内に Python の最小テトリスを作成する（コンソール版）。",
        "成果物は `tetris/main.py` の1ファイルで完結させる。",
        "Production リポジトリや開発 worktree には書き込まない。",
        "起動方法（実行コマンド）を最終回答に記載する。",
        "スコア表示・ライン消去・ピース落下の最小ループを含める。",
    ],
    "non_goals": [
        "GUI 版テトリス",
        "ネットワーク対戦",
        "Production / dev worktree への直接書き込み",
    ],
    "acceptance_criteria": [
        "`tetris/main.py` が Sandbox 内に存在する。",
        "ファイルは単体で Python 実行可能な構造である。",
    ],
}


@dataclass
class GrillTurn:
    round: int
    dimension: str
    question: str
    recommended_answer: str
    selected_answer: str
    selection_policy: str = TEST_AUTO_RECOMMENDATION_POLICY
    human_response_kind: str = SIMULATED_HUMAN_RESPONSE_KIND
    question_contract: dict[str, Any] = field(default_factory=dict)
    selection_result: dict[str, Any] = field(default_factory=dict)


@dataclass
class GrillMeResult:
    initial_request: str
    mode: str
    threshold: float
    transcript: list[GrillTurn] = field(default_factory=list)
    ambiguity_report: dict[str, Any] = field(default_factory=dict)
    aligned_spec: dict[str, Any] = field(default_factory=dict)
    implementation_prompt: str = ""
    gate_passed: bool = False
    rounds: int = 0
    source: str = "grill_me_loop"
    fallback_used: bool = False
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["transcript"] = [asdict(item) for item in self.transcript]
        return payload


@dataclass
class ProductionGrillStepResult:
    """One resumable Production Human-UI step; Chat Session is the carrier."""

    status: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    ambiguity_report: dict[str, Any] = field(default_factory=dict)
    aligned_spec: dict[str, Any] = field(default_factory=dict)
    generated_aligned_spec: dict[str, Any] = field(default_factory=dict)
    semantic_preservation: dict[str, Any] = field(default_factory=dict)
    question_contract: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def threshold_for_mode(mode: str) -> float:
    return THRESHOLDS.get(mode, THRESHOLDS["freeform"])


def mean_score(dimensions: Mapping[str, float]) -> float:
    values = [float(dimensions[key]) for key in DIMENSIONS if key in dimensions]
    if not values:
        return 1.0
    return sum(values) / len(values)


def gate_passed(aggregate: float, mode: str) -> bool:
    return aggregate <= threshold_for_mode(mode)


def _strip_json_fence(text: str) -> str:
    return strip_json_fence(text)


def build_implementation_prompt(spec: Mapping[str, Any]) -> str:
    title = str(spec.get("title") or "Implementation request").strip()
    summary = str(spec.get("summary") or "").strip()
    conditions = [str(item).strip() for item in (spec.get("numbered_conditions") or []) if str(item).strip()]
    non_goals = [str(item).strip() for item in (spec.get("non_goals") or []) if str(item).strip()]
    acceptance = [
        str(item).strip() for item in (spec.get("acceptance_criteria") or []) if str(item).strip()
    ]

    lines = [title]
    if summary:
        lines.extend(["", summary])
    if conditions:
        lines.extend(["", "完了条件:"])
        lines.extend(f"{index}. {item}" for index, item in enumerate(conditions, 1))
    if non_goals:
        lines.extend(["", "非目標:"])
        lines.extend(f"- {item}" for item in non_goals)
    if acceptance:
        lines.extend(["", "受け入れ基準:"])
        lines.extend(f"- {item}" for item in acceptance)
    return "\n".join(lines).strip()


def _message_content(response: Any) -> str:
    return message_content(response)


def _call_llm_json(
    *,
    model: str,
    system: str,
    user: str,
    chat_fn: Callable[..., Any] | None = None,
    observer: PipelineObserver | None = None,
    skill_id: str = "grill-me",
    round_index: int | None = None,
    llm_step: str = "call",
) -> dict[str, Any]:
    fn = chat_fn or llm_chat

    def _invoke() -> dict[str, Any]:
        last_empty: LLMEmptyResponseError | None = None
        for attempt in range(LLM_JSON_MAX_ATTEMPTS):
            response = fn(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                format="json",
                execution_profile="human_intent",
            )
            diagnostics = llm_response_diagnostics(response)
            diagnostics["attempt"] = attempt + 1
            try:
                return parse_json_content(
                    _message_content(response),
                    diagnostics=diagnostics,
                )
            except LLMEmptyResponseError as exc:
                last_empty = exc
                if attempt + 1 >= LLM_JSON_MAX_ATTEMPTS:
                    raise
        if last_empty is not None:
            raise last_empty
        raise LLMEmptyResponseError("LLM JSON call produced no payload")

    return observed_llm_json(
        observer,
        phase=PHASE1_GRILL,
        skill_id=skill_id,
        model=model,
        round_index=round_index,
        call_llm=_invoke,
    )


def _conversation_block(transcript: list[GrillTurn]) -> str:
    if not transcript:
        return "(no prior answers)"
    rows = []
    for item in transcript:
        rows.append(f"Q{item.round} [{item.dimension}]: {item.question}")
        rows.append(
            f"A{item.round} ({item.human_response_kind}/{item.selection_policy}): {item.selected_answer}"
        )
    return "\n".join(rows)


def format_production_prior_context(
    structured_requirements: Sequence[Mapping[str, Any]] | None,
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None,
) -> str:
    """Build a prompt-only view of Mission canonical data, not a second source of truth."""
    requirements = [
        {
            key: row.get(key)
            for key in (
                "requirement_id", "source_text", "disposition", "resolution_status",
                "normalized_meaning", "provenance", "materiality",
            )
            if key in row
        }
        for row in (structured_requirements or [])
        if isinstance(row, Mapping)
    ]
    decisions = [dict(row) for row in (confirmed_clarifications or []) if isinstance(row, Mapping)]
    return json.dumps(
        {
            "canonical_structured_requirements": requirements,
            "confirmed_human_decisions": decisions,
        },
        ensure_ascii=False,
        indent=2,
    )


def _production_transcript_block(transcript: Sequence[Mapping[str, Any]]) -> str:
    if not transcript:
        return "(no prior answers)"
    lines: list[str] = []
    for index, row in enumerate(transcript, 1):
        lines.append(f"Q{index} [{row.get('dimension') or 'goals'}]: {row.get('question') or ''}")
        lines.append(f"A{index} (human_ui): {row.get('selected_answer') or ''}")
    return "\n".join(lines)


def _resolved_requirement_meanings(
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> list[str]:
    meanings: list[str] = []
    for row in structured_requirements or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("resolution_status") or "") not in {"resolved", "waived_by_human"}:
            continue
        if str(row.get("disposition") or "") in {"NOISE", "CONTEXT"}:
            continue
        meaning = str(row.get("normalized_meaning") or row.get("source_text") or "").strip()
        if meaning and meaning not in meanings:
            meanings.append(meaning)
    return meanings


def validate_resolved_requirement_meanings(
    aligned_spec: Mapping[str, Any] | None,
    *,
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Inspect generated output without repairing or otherwise mutating it."""
    aligned = dict(aligned_spec or {})
    represented = "\n".join(
        str(item)
        for key in ("summary", "numbered_conditions", "acceptance_criteria")
        for item in (
            [aligned.get(key)]
            if key == "summary"
            else (aligned.get(key) or [])
        )
        if str(item).strip()
    )
    requirements: list[dict[str, Any]] = []
    for row in structured_requirements or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("resolution_status") or "") not in {"resolved", "waived_by_human"}:
            continue
        if str(row.get("disposition") or "") in {"NOISE", "CONTEXT"}:
            continue
        normalized = str(row.get("normalized_meaning") or "").strip()
        source = str(row.get("source_text") or "").strip()
        required = normalized or source
        if not required:
            continue
        if required in represented:
            status = "preserved"
        elif normalized and source and source in represented:
            status = "ambiguous"
        else:
            status = "missing"
        requirements.append(
            {
                "requirement_id": str(row.get("requirement_id") or ""),
                "status": status,
                "required_meaning": required,
            }
        )
    statuses = {row["status"] for row in requirements}
    overall = "missing" if "missing" in statuses else "ambiguous" if "ambiguous" in statuses else "preserved"
    return {"status": overall, "requirements": requirements}


def project_canonical_requirements_to_aligned_spec(
    aligned_spec: Mapping[str, Any] | None,
    *,
    initial_request: str,
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Project Mission-canonical meanings into the existing aligned_spec shape."""
    aligned = dict(aligned_spec or {})
    aligned.setdefault("title", "Implementation goal")
    aligned.setdefault("summary", initial_request)
    aligned.setdefault("non_goals", [])
    aligned.setdefault("acceptance_criteria", [])
    numbered = [str(item) for item in (aligned.get("numbered_conditions") or []) if str(item).strip()]
    acceptance = [str(item) for item in (aligned.get("acceptance_criteria") or []) if str(item).strip()]
    represented = "\n".join([*numbered, *acceptance])
    for meaning in _resolved_requirement_meanings(structured_requirements):
        if meaning not in represented:
            numbered.append(meaning)
            represented += "\n" + meaning
    aligned["numbered_conditions"] = numbered or [initial_request]
    return aligned


def preserve_resolved_requirement_meanings(
    aligned_spec: Mapping[str, Any] | None,
    *,
    initial_request: str,
    structured_requirements: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Compatibility alias for the explicitly named canonical projection."""
    return project_canonical_requirements_to_aligned_spec(
        aligned_spec,
        initial_request=initial_request,
        structured_requirements=structured_requirements,
    )


def _normalize_dimensions(raw: Mapping[str, Any]) -> dict[str, float]:
    aliases = {
        "goal": "goals",
        "goals": "goals",
        "acceptance": "acceptance",
        "boundaries": "boundaries",
        "boundary": "boundaries",
        "alternatives": "alternatives",
        "alternative": "alternatives",
        "assumptions": "assumptions",
        "assumption": "assumptions",
    }
    out: dict[str, float] = {}
    for key, value in raw.items():
        normalized = aliases.get(str(key).strip().casefold())
        if normalized is None:
            continue
        out[normalized] = float(value)
    for key in DIMENSIONS:
        out.setdefault(key, 0.5)
    return out


def _question_system_prompt(mode: str) -> str:
    threshold = threshold_for_mode(mode)
    return (
        "You are running the grill-me interview skill for an autonomous E2E harness.\n"
        "Ask exactly ONE question per response in JSON.\n"
        "Each question must include a recommended_answer that the harness will auto-select.\n"
        "Target dimensions: Goals, Acceptance, Boundaries, Alternatives, Assumptions.\n"
        f"Mode: {mode}. Exit threshold aggregate <= {threshold}.\n"
        "Prefer concrete, verifiable answers. For this repository, implementation happens in "
        "Dedicated Sandbox via Production Chat create_file, not in the dev worktree.\n"
        "Respond ONLY with JSON using keys: question, recommended_answer, dimension, rationale.\n"
        "Optional future keys: options (array of {id, label}), recommended_option_id, recommendation_reason."
    )


def _score_system_prompt(mode: str) -> str:
    threshold = threshold_for_mode(mode)
    return (
        "You are scoring a grill-me interview for an autonomous E2E harness.\n"
        "Use scores 0, 0.25, 0.5, 0.75, or 1.0 for each dimension.\n"
        f"Mode: {mode}. gate_passes when aggregate <= {threshold}.\n"
        "Respond ONLY with JSON using keys:\n"
        "dimensions (object with goals, acceptance, boundaries, alternatives, assumptions),\n"
        "aggregate (number),\n"
        "weakest (array of strings),\n"
        "ready_to_exit (boolean),\n"
        "aligned_spec (object with title, summary, numbered_conditions, non_goals, acceptance_criteria)."
    )


def _merge_aligned_spec(
    aligned_spec: Mapping[str, Any] | None,
    fallback: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(fallback)
    for key, value in dict(aligned_spec or {}).items():
        if value:
            merged[key] = value
    if not merged.get("numbered_conditions"):
        merged["numbered_conditions"] = list(fallback.get("numbered_conditions") or [])
    return merged


def run_production_grill_me_step(
    initial_request: str,
    *,
    structured_requirements: Sequence[Mapping[str, Any]] | None,
    confirmed_clarifications: Sequence[Mapping[str, Any]] | None,
    transcript: Sequence[Mapping[str, Any]] | None,
    model: str,
    chat_fn: Callable[..., Any] | None = None,
    mode: str = "spec",
) -> ProductionGrillStepResult:
    """Score once, then finish or emit exactly one unanswered Human-UI question."""
    prior = format_production_prior_context(structured_requirements, confirmed_clarifications)
    history = [dict(row) for row in (transcript or []) if isinstance(row, Mapping)]
    locked = (
        "Canonical prior context is authoritative. Resolved requirements and confirmed human "
        "decisions are LOCKED. Preserve them and never ask the human to define or confirm them "
        "again. Ask only about a still-unanswered material ambiguity."
    )
    score_payload = _call_llm_json(
        model=model,
        system=_score_system_prompt(mode) + "\n\n" + locked,
        user=(
            f"Initial request:\n{initial_request}\n\nCanonical prior context:\n{prior}\n\n"
            f"Production Human conversation:\n{_production_transcript_block(history)}\n\n"
            "Score the current artifact. If the gate passes, emit aligned_spec and preserve every "
            "resolved normalized_meaning verbatim in numbered_conditions or acceptance_criteria."
        ),
        chat_fn=chat_fn,
    )
    dimensions = _normalize_dimensions(score_payload.get("dimensions") or {})
    aggregate = float(score_payload.get("aggregate") or mean_score(dimensions))
    report = {
        "dimensions": dimensions,
        "aggregate": aggregate,
        "threshold": threshold_for_mode(mode),
        "weakest": list(score_payload.get("weakest") or []),
        "ready_to_exit": bool(score_payload.get("ready_to_exit")),
    }
    if gate_passed(aggregate, mode):
        raw = score_payload.get("aligned_spec")
        generated = dict(raw) if isinstance(raw, Mapping) else {}
        generated_validation = validate_resolved_requirement_meanings(
            generated,
            structured_requirements=structured_requirements,
        )
        aligned = project_canonical_requirements_to_aligned_spec(
            generated,
            initial_request=initial_request,
            structured_requirements=structured_requirements,
        )
        final_validation = validate_resolved_requirement_meanings(
            aligned,
            structured_requirements=structured_requirements,
        )
        return ProductionGrillStepResult(
            status="aligned",
            transcript=history,
            ambiguity_report=report,
            aligned_spec=aligned,
            generated_aligned_spec=generated,
            semantic_preservation={
                "generated": generated_validation,
                "final": final_validation,
                "canonical_projection_applied": aligned != generated,
            },
        )

    round_index = len(history) + 1
    question_payload: dict[str, Any] | None = None
    rejected_questions: list[str] = []
    for _attempt in range(3):
        candidate = _call_llm_json(
            model=model,
            system=_question_system_prompt(mode) + "\n\n" + locked,
            user=(
                f"Initial request:\n{initial_request}\n\nCanonical prior context:\n{prior}\n\n"
                f"Production Human conversation:\n{_production_transcript_block(history)}\n\n"
                f"Rejected duplicate questions:\n{json.dumps(rejected_questions, ensure_ascii=False)}\n\n"
                "Ask exactly one highest-value unanswered question. Do not restate or re-open a "
                "resolved requirement or confirmed decision."
            ),
            chat_fn=chat_fn,
        )
        audit = _call_llm_json(
            model=model,
            system=(
                "You are a semantic duplicate-question auditor. Compare the candidate question "
                "with the canonical resolved requirements and confirmed decisions. Return JSON "
                "with reasks_resolved (boolean) and reason. True means the candidate asks the "
                "human to define, confirm, or choose a meaning already resolved."
            ),
            user=f"Canonical prior context:\n{prior}\n\nCandidate question:\n{candidate.get('question') or ''}",
            chat_fn=chat_fn,
        )
        if audit.get("reasks_resolved") is False:
            question_payload = candidate
            break
        rejected_questions.append(str(candidate.get("question") or ""))
    if question_payload is None:
        raise ValueError("grill-me generated only questions that re-open resolved requirements")
    dimension = str(question_payload.get("dimension") or "goals").strip().casefold()
    contract = normalize_grill_question_payload(
        question_payload,
        question_id=f"production_grill_me:r{round_index}",
        grill_reason=GRILL_REASON_INITIAL,
        dimension=dimension,
    )
    contract.decision_key = str(question_payload.get("decision_key") or f"spec:{dimension}")
    contract.decision_subject = str(question_payload.get("decision_subject") or dimension)
    return ProductionGrillStepResult(
        status="awaiting_human",
        transcript=history,
        ambiguity_report=report,
        question_contract=contract.as_dict(),
    )


def run_grill_me_loop(
    initial_request: str,
    *,
    model: str,
    mode: str = "freeform",
    max_rounds: int = 8,
    min_rounds_before_score: int = 3,
    max_score_failures: int = 2,
    auto_select: str = "recommended",
    chat_fn: Callable[..., Any] | None = None,
    fallback_spec: Mapping[str, Any] | None = None,
    observer: PipelineObserver | None = None,
) -> GrillMeResult:
    """Run a bounded grill-me loop and return an aligned implementation prompt."""
    result = GrillMeResult(
        initial_request=initial_request,
        mode=mode,
        threshold=threshold_for_mode(mode),
    )
    transcript: list[GrillTurn] = []
    fallback = dict(fallback_spec or TETRIS_FALLBACK_SPEC)
    score_failures = 0

    for round_index in range(1, max_rounds + 1):
        try:
            question_payload = _call_llm_json(
                model=model,
                system=_question_system_prompt(mode),
                user=(
                    f"Initial request:\n{initial_request}\n\n"
                    f"Conversation so far:\n{_conversation_block(transcript)}\n\n"
                    "Ask the next highest-value unresolved question."
                ),
                chat_fn=chat_fn,
                observer=observer,
                round_index=round_index,
                llm_step="question",
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"question_round_{round_index}: {type(exc).__name__}: {exc}")
            break

        dimension = str(question_payload.get("dimension") or "goals").strip().casefold()
        try:
            contract = normalize_grill_question_payload(
                question_payload,
                question_id=f"initial_grill:r{round_index}",
                grill_reason=GRILL_REASON_INITIAL,
                dimension=dimension,
            )
        except ValueError as exc:
            result.errors.append(f"question_round_{round_index}: {exc}")
            break

        policy = (
            TEST_AUTO_RECOMMENDATION_POLICY
            if auto_select in {"recommended", TEST_AUTO_RECOMMENDATION_POLICY}
            else auto_select
        )
        try:
            selection = apply_selection_policy(contract, policy)
        except ValueError as exc:
            result.errors.append(f"question_round_{round_index}: {exc}")
            break

        recommended = contract.recommended_option()
        recommended_answer = recommended.label if recommended is not None else ""
        selected = str(selection.selected_label or "")
        transcript.append(
            GrillTurn(
                round=round_index,
                dimension=dimension,
                question=contract.question,
                recommended_answer=recommended_answer,
                selected_answer=selected,
                selection_policy=selection.selection_policy,
                human_response_kind=selection.human_response_kind,
                question_contract=contract.as_dict(),
                selection_result=selection.as_dict(),
            )
        )

        if round_index < min_rounds_before_score:
            continue

        try:
            score_payload = _call_llm_json(
                model=model,
                system=_score_system_prompt(mode),
                user=(
                    f"Initial request:\n{initial_request}\n\n"
                    f"Resolved conversation:\n{_conversation_block(transcript)}\n\n"
                    "Score the artifact and, if ready, emit aligned_spec with numbered_conditions."
                ),
                chat_fn=chat_fn,
                observer=observer,
                round_index=round_index,
                llm_step="score",
            )
        except Exception as exc:  # noqa: BLE001
            score_failures += 1
            result.errors.append(f"score_round_{round_index}: {type(exc).__name__}: {exc}")
            if score_failures >= max_score_failures or round_index >= max_rounds:
                break
            continue

        dimensions = _normalize_dimensions(score_payload.get("dimensions") or {})
        aggregate = float(score_payload.get("aggregate") or mean_score(dimensions))
        aligned_raw = score_payload.get("aligned_spec")
        aligned_spec = aligned_raw if isinstance(aligned_raw, dict) else {}

        report = {
            "dimensions": dimensions,
            "aggregate": aggregate,
            "threshold": result.threshold,
            "weakest": list(score_payload.get("weakest") or []),
            "ready_to_exit": bool(score_payload.get("ready_to_exit")),
        }
        passed = gate_passed(aggregate, mode)
        ready = bool(score_payload.get("ready_to_exit"))

        result.transcript = list(transcript)
        result.rounds = round_index
        result.ambiguity_report = report

        if passed:
            merged = _merge_aligned_spec(aligned_spec, fallback)
            result.aligned_spec = merged
            result.implementation_prompt = build_implementation_prompt(merged)
            result.gate_passed = True
            if not ready:
                result.errors.append("ready_to_exit_false_but_gate_passed")
            if not aligned_spec.get("numbered_conditions"):
                result.errors.append("aligned_spec_missing_numbered_conditions_merged_fallback")
            return result

        if round_index >= max_rounds:
            break

    result.transcript = list(transcript)
    result.rounds = len(transcript)
    result.fallback_used = True
    result.aligned_spec = dict(fallback)
    result.implementation_prompt = build_implementation_prompt(fallback)
    result.ambiguity_report = {
        "dimensions": {key: 0.25 for key in DIMENSIONS},
        "aggregate": 0.25,
        "threshold": result.threshold,
        "weakest": [],
        "ready_to_exit": True,
        "note": "fallback_spec_applied",
    }
    result.gate_passed = gate_passed(0.25, mode)
    if not result.errors:
        result.errors.append("grill_loop_exhausted_or_parse_failure")
    return result


__all__ = [
    "DIMENSIONS",
    "PHASE1_GRILL",
    "SIMULATED_HUMAN_RESPONSE_KIND",
    "TEST_AUTO_RECOMMENDATION_POLICY",
    "THRESHOLDS",
    "TETRIS_FALLBACK_SPEC",
    "TETRIS_VAGUE_REQUEST",
    "GrillMeResult",
    "GrillTurn",
    "ProductionGrillStepResult",
    "build_implementation_prompt",
    "format_production_prior_context",
    "gate_passed",
    "mean_score",
    "parse_json_content",
    "run_grill_me_loop",
    "run_production_grill_me_step",
    "validate_resolved_requirement_meanings",
    "project_canonical_requirements_to_aligned_spec",
    "preserve_resolved_requirement_meanings",
    "threshold_for_mode",
]
