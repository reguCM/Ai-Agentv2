"""Independent Lab harness for semantic revalidation failure classification and retry."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai_tool.decision_premise_revalidation import (
    _build_revalidation_prompt,
    build_premise_revalidation_case,
)
from ai_tool.llm_json_parse import llm_response_diagnostics
from ai_tool.revalidation_failure_class import (
    classify_revalidation_failure,
    is_mechanical_retry_candidate,
    is_resolved_outcome,
    is_semantic_only_failure,
    is_unnecessary_escalation_candidate,
)
from ai_tool.revalidation_protocol import (
    evaluate_semantic_revalidation_llm,
    semantic_revalidation_result_missing_chat_fn,
    semantic_revalidation_result_missing_inputs,
)
from ai_tool.task_upstream_supersession_revalidation import (
    _build_upstream_supersession_wave_prompt,
    evaluate_upstream_supersession,
)

PRIMARY_LOCAL_MODEL = "qwen3_8b"
STRONGER_LOCAL_MODEL = "qwen3_14b"
EXECUTION_PROFILE = "structured_output"
LAB0_MAX_RETRY = 1


@dataclass
class RevalidationLabFixture:
    case_id: str
    domain: str
    description: str
    case: dict[str, Any]
    evaluate_fn: str
    oracle_outcome: str | None = None
    second_pass_payload: dict[str, Any] | None = None


@dataclass
class RevalidationLabObservation:
    arm: str
    case_id: str
    domain: str
    model_id: str
    execution_profile: str
    attempt: int
    failure_class: str
    outcome: str | None
    reason: str | None
    prompt_chars: int
    latency_ms: float
    response_diagnostics: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    retried: bool = False
    oracle_outcome: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _prompt_chars_for_fixture(fixture: RevalidationLabFixture) -> int:
    if fixture.evaluate_fn == "premise":
        return len(_build_revalidation_prompt(fixture.case))
    if fixture.evaluate_fn == "upstream":
        return len(_build_upstream_supersession_wave_prompt(fixture.case))
    return 0


def _evaluate_fixture(
    fixture: RevalidationLabFixture,
    *,
    chat_fn: Callable[..., Any] | None,
    model: str,
    capture: dict[str, Any],
) -> tuple[dict[str, Any] | None, BaseException | None]:
    missing = list(fixture.case.get("missing_fields") or [])
    if missing:
        return semantic_revalidation_result_missing_inputs(missing), None
    if chat_fn is None:
        return semantic_revalidation_result_missing_chat_fn(), None

    def _chat_with_capture(**kwargs: Any) -> Any:
        response = chat_fn(**kwargs)
        capture["response"] = response
        return response

    if fixture.evaluate_fn == "premise":
        return (
            evaluate_semantic_revalidation_llm(
                prompt=_build_revalidation_prompt(fixture.case),
                chat_fn=_chat_with_capture,
                model=model,
                num_predict=800,
            ),
            None,
        )
    if fixture.evaluate_fn == "upstream":
        return (
            evaluate_upstream_supersession(
                fixture.case,
                chat_fn=_chat_with_capture,
                model=model,
            ),
            None,
        )
    raise ValueError(f"unknown evaluate_fn: {fixture.evaluate_fn}")


def run_single_evaluation(
    fixture: RevalidationLabFixture,
    *,
    arm: str,
    chat_fn: Callable[..., Any] | None,
    model: str = PRIMARY_LOCAL_MODEL,
    attempt: int = 1,
    retried: bool = False,
) -> tuple[RevalidationLabObservation, dict[str, Any] | None, BaseException | None]:
    capture: dict[str, Any] = {"response": None}
    prompt_chars = _prompt_chars_for_fixture(fixture)
    started = time.perf_counter()
    try:
        result, error = _evaluate_fixture(
            fixture,
            chat_fn=chat_fn,
            model=model,
            capture=capture,
        )
    except BaseException as exc:  # noqa: BLE001
        result = None
        error = exc
    latency_ms = (time.perf_counter() - started) * 1000.0
    failure_class = classify_revalidation_failure(result, error=error)
    observation = RevalidationLabObservation(
        arm=arm,
        case_id=fixture.case_id,
        domain=fixture.domain,
        model_id=model,
        execution_profile=EXECUTION_PROFILE,
        attempt=attempt,
        failure_class=failure_class,
        outcome=str((result or {}).get("outcome") or "") or None,
        reason=str((result or {}).get("reason") or "") or None,
        prompt_chars=prompt_chars,
        latency_ms=latency_ms,
        response_diagnostics=llm_response_diagnostics(capture.get("response"))
        if capture.get("response") is not None
        else {},
        error_type=error.__class__.__name__ if error is not None else None,
        retried=retried,
        oracle_outcome=fixture.oracle_outcome,
    )
    return observation, result if isinstance(result, dict) else None, error


def run_arm_a(
    fixtures: Sequence[RevalidationLabFixture],
    *,
    chat_fn_for: Callable[[RevalidationLabFixture], Callable[..., Any] | None],
    model: str = PRIMARY_LOCAL_MODEL,
) -> list[RevalidationLabObservation]:
    observations: list[RevalidationLabObservation] = []
    for fixture in fixtures:
        obs, _, _ = run_single_evaluation(
            fixture,
            arm="A",
            chat_fn=chat_fn_for(fixture),
            model=model,
            attempt=1,
        )
        observations.append(obs)
    return observations


def run_arm_b(
    fixtures: Sequence[RevalidationLabFixture],
    *,
    chat_fn_for: Callable[[RevalidationLabFixture], Callable[..., Any] | None],
    model: str = PRIMARY_LOCAL_MODEL,
    max_retry: int = LAB0_MAX_RETRY,
) -> list[RevalidationLabObservation]:
    observations: list[RevalidationLabObservation] = []
    for fixture in fixtures:
        obs1, result1, error1 = run_single_evaluation(
            fixture,
            arm="B",
            chat_fn=chat_fn_for(fixture),
            model=model,
            attempt=1,
        )
        observations.append(obs1)
        failure_class = classify_revalidation_failure(result1, error=error1)
        if max_retry < 1 or not is_mechanical_retry_candidate(failure_class):
            continue
        if fixture.second_pass_payload is None:
            continue
        obs2, _, _ = run_single_evaluation(
            fixture,
            arm="B",
            chat_fn=_retry_chat_fn(fixture),
            model=model,
            attempt=2,
            retried=True,
        )
        observations.append(obs2)
    return observations


def _retry_chat_fn(fixture: RevalidationLabFixture) -> Callable[..., Any]:
    import json
    from types import SimpleNamespace

    payload = dict(fixture.second_pass_payload or {})

    def chat(**_kwargs: Any) -> Any:
        return SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        )

    return chat


def summarize_lab0_results(
    observations: Sequence[RevalidationLabObservation],
) -> dict[str, Any]:
    by_arm: dict[str, list[RevalidationLabObservation]] = {"A": [], "B": []}
    for row in observations:
        by_arm.setdefault(row.arm, []).append(row)

    def _final_per_case(rows: Sequence[RevalidationLabObservation]) -> list[RevalidationLabObservation]:
        grouped: dict[str, RevalidationLabObservation] = {}
        for row in rows:
            grouped[row.case_id] = row
        return list(grouped.values())

    failure_counts: dict[str, int] = {}
    for row in observations:
        failure_counts[row.failure_class] = failure_counts.get(row.failure_class, 0) + 1

    def _arm_metrics(arm: str) -> dict[str, Any]:
        finals = _final_per_case(by_arm.get(arm, []))
        total = len(finals)
        resolved = sum(1 for row in finals if is_resolved_outcome({"outcome": row.outcome}))
        cannot_determine = sum(
            1 for row in finals if str(row.outcome or "") == "cannot_determine"
        )
        oracle_hits = sum(
            1
            for row in finals
            if row.oracle_outcome and row.outcome == row.oracle_outcome
        )
        oracle_total = sum(1 for row in finals if row.oracle_outcome)
        retried = [row for row in observations if row.arm == arm and row.retried]
        retry_effective = sum(
            1
            for row in retried
            if is_resolved_outcome({"outcome": row.outcome})
        )
        return {
            "cases": total,
            "resolved_count": resolved,
            "success_rate": (resolved / total) if total else 0.0,
            "cannot_determine_count": cannot_determine,
            "cannot_determine_resolution_rate": (
                1.0 - (cannot_determine / total) if total else 0.0
            ),
            "oracle_match_rate": (oracle_hits / oracle_total) if oracle_total else None,
            "retry_attempts": len(retried),
            "retry_effective_count": retry_effective,
            "retry_effectiveness_rate": (
                retry_effective / len(retried) if retried else None
            ),
        }

    semantic_only = [
        row.case_id
        for row in _final_per_case(by_arm.get("A", []))
        if is_semantic_only_failure(row.failure_class)
    ]
    escalation_candidates = [
        row.case_id
        for row in _final_per_case(by_arm.get("A", []))
        if is_unnecessary_escalation_candidate(
            failure_class=row.failure_class,
            final_outcome={"outcome": row.outcome},
        )
    ]

    arm_a = _arm_metrics("A")
    arm_b = _arm_metrics("B")
    lab1_ready = bool(semantic_only) and arm_a["cases"] > 0

    return {
        "failure_class_counts": failure_counts,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "semantic_only_case_ids": semantic_only,
        "unnecessary_escalation_candidate_case_ids": escalation_candidates,
        "lab1_ready": lab1_ready,
        "lab1_ready_reason": (
            "semantic-only subset extracted from Arm A finals"
            if lab1_ready
            else "no semantic-only cases observed"
        ),
    }


def write_observations_jsonl(
    observations: Sequence[RevalidationLabObservation],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in observations:
            handle.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
    return path


def build_lab0_fixtures(
    orchestrator: Any,
    *,
    extra_fixtures: Sequence[RevalidationLabFixture] | None = None,
) -> list[RevalidationLabFixture]:
    """Build deterministic fixture set from existing revalidation seeds."""
    fixtures: list[RevalidationLabFixture] = []
    premise_case = build_premise_revalidation_case(orchestrator, "gh-T2")
    if premise_case is None:
        return list(extra_fixtures or [])

    fixtures.extend(
        [
            RevalidationLabFixture(
                case_id="premise-semantic-ambiguous",
                domain="premise",
                description="LLM explicit cannot_determine on premise revalidation",
                case=premise_case,
                evaluate_fn="premise",
                oracle_outcome="cannot_determine",
            ),
            RevalidationLabFixture(
                case_id="premise-still-valid",
                domain="premise",
                description="Resolved still_valid baseline",
                case=premise_case,
                evaluate_fn="premise",
                oracle_outcome="still_valid",
            ),
            RevalidationLabFixture(
                case_id="premise-system-missing-inputs",
                domain="premise",
                description="System missing required inputs",
                case={**premise_case, "missing_fields": ["decision_premises"]},
                evaluate_fn="premise",
                oracle_outcome="cannot_determine",
            ),
            RevalidationLabFixture(
                case_id="premise-system-not-configured",
                domain="premise",
                description="chat_fn not configured",
                case=dict(premise_case),
                evaluate_fn="premise",
                oracle_outcome="cannot_determine",
            ),
            RevalidationLabFixture(
                case_id="premise-llm-schema-failure",
                domain="premise",
                description="Invalid LLM schema on first pass, still_valid on retry",
                case=dict(premise_case),
                evaluate_fn="premise",
                oracle_outcome="still_valid",
                second_pass_payload={"outcome": "still_valid", "reason": "retry recovered"},
            ),
            RevalidationLabFixture(
                case_id="premise-llm-empty-response",
                domain="premise",
                description="Empty LLM response on first pass, still_valid on retry",
                case=dict(premise_case),
                evaluate_fn="premise",
                oracle_outcome="still_valid",
                second_pass_payload={"outcome": "still_valid", "reason": "retry recovered"},
            ),
            RevalidationLabFixture(
                case_id="premise-llm-parse-failure",
                domain="premise",
                description="Non-JSON response on first pass, still_valid on retry",
                case=dict(premise_case),
                evaluate_fn="premise",
                oracle_outcome="still_valid",
                second_pass_payload={"outcome": "still_valid", "reason": "retry recovered"},
            ),
            RevalidationLabFixture(
                case_id="premise-unknown-outcome",
                domain="premise",
                description="Unknown outcome token on first pass, still_valid on retry",
                case=dict(premise_case),
                evaluate_fn="premise",
                oracle_outcome="still_valid",
                second_pass_payload={"outcome": "still_valid", "reason": "retry recovered"},
            ),
        ]
    )
    if extra_fixtures:
        fixtures.extend(extra_fixtures)
    return fixtures


def routing_chat_for_fixture(fixture: RevalidationLabFixture) -> Callable[..., Any]:
    """Deterministic chat_fn router for Lab-0 synthetic failures."""
    import json
    from types import SimpleNamespace

    case_id = fixture.case_id

    def chat(**_kwargs: Any) -> Any:
        if case_id == "premise-semantic-ambiguous":
            payload = {
                "outcome": "cannot_determine",
                "reason": "Evidence is insufficient to decide.",
            }
        elif case_id == "premise-still-valid":
            payload = {"outcome": "still_valid", "reason": "Task remains valid."}
        elif case_id == "premise-llm-schema-failure":
            payload = {"unexpected": "no outcome field"}
        elif case_id == "premise-llm-empty-response":
            return SimpleNamespace(message=SimpleNamespace(content=""))
        elif case_id == "premise-llm-parse-failure":
            return SimpleNamespace(message=SimpleNamespace(content="not-json"))
        elif case_id == "premise-unknown-outcome":
            payload = {"outcome": "maybe_valid", "reason": "unknown token"}
        elif case_id == "upstream-semantic-ambiguous":
            payload = {
                "outcome": "cannot_determine",
                "reason": "Upstream change effect is unclear.",
            }
        else:
            payload = {"outcome": "still_valid", "reason": "default"}
        return SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        )

    return chat


def chat_fn_for_fixture(fixture: RevalidationLabFixture) -> Callable[..., Any] | None:
    if fixture.case_id == "premise-system-not-configured":
        return None
    return routing_chat_for_fixture(fixture)


def seed_lab0_handoff_orchestrator(store: Any) -> Any:
    """Seed one handoff orchestrator with stale premise state for Lab-0."""
    from ai_tool.chat_interface.decision_change_gate import (
        DECISION_STATUS_CONFIRMED,
        supersede_decision,
    )
    from ai_tool.chat_interface.task_orchestration import ChatTaskOrchestrator
    from ai_tool.dev_skill_pipeline import normalize_implementation_tasks
    from ai_tool.goal_handoff_runtime_bridge import seed_orchestrator_from_handoff
    from ai_tool.mission_memory.chat_persist import bind_execution_identity, persist_chat_execution
    from ai_tool.production_handoff_bridge import (
        build_production_handoff_packet,
        prepare_production_handoff_orchestrator,
    )

    key_json = "acceptance:output_format"
    d_json_v1 = "d-json-v1"
    d_json_v2 = "d-json-v2"
    d_gui_v1 = "d-gui-v1"
    decisions = [
        {
            "decision_id": d_json_v1,
            "decision_key": key_json,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "JSON",
            "dimension": "acceptance",
        },
        {
            "decision_id": d_gui_v1,
            "decision_key": "scope:gui",
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "GUIあり",
            "dimension": "scope",
        },
    ]
    plan_tasks = normalize_implementation_tasks(
        [
            {
                "id": "T1",
                "title": "Shared setup",
                "acceptance": ["project scaffold exists"],
                "verification": ["repo ready"],
                "dependencies": [],
                "size": "S",
            },
            {
                "id": "T2",
                "title": "Emit JSON API output",
                "acceptance": ["JSON response available"],
                "verification": ["json endpoint returns payload"],
                "dependencies": ["T1"],
                "size": "S",
                "premise_decision_keys": [key_json],
            },
            {
                "id": "T3",
                "title": "Build GUI surface",
                "acceptance": ["GUI visible"],
                "verification": ["ui renders"],
                "dependencies": ["T1"],
                "size": "S",
                "premise_decision_keys": ["scope:gui"],
            },
        ],
        default_acceptance=["done"],
        default_verification=["check"],
    )

    exec1 = ChatTaskOrchestrator("exec-lab0-1", "build service")
    bind_execution_identity(exec1)
    exec1.confirmed_clarifications = list(decisions)
    recorded = persist_chat_execution(
        exec1,
        stop_reason="DETERMINED",
        determined=True,
        answer="decisions saved",
        store=store,
    )
    exec2 = ChatTaskOrchestrator("exec-lab0-2", "build service")
    bind_execution_identity(exec2, resume_mission_id=recorded["mission_id"])
    prepare_production_handoff_orchestrator(exec2, store=store)
    packet = build_production_handoff_packet(
        exec2,
        initial_request="build service",
        plan={"tasks": plan_tasks},
        tech_spec={"summary": "service"},
        store=store,
        handoff_slug="revalidation-lab0",
    )
    exec2.confirmed_clarifications = list(decisions)
    seed_orchestrator_from_handoff(exec2, packet)
    exec2.runtime.evaluate_task("gh-T1", ["project scaffold exists", "repo ready"])
    supersede_decision(
        exec2,
        d_json_v1,
        {
            "decision_id": d_json_v2,
            "decision_key": key_json,
            "status": DECISION_STATUS_CONFIRMED,
            "source": "boundary_grill",
            "text": "Markdown",
            "dimension": "acceptance",
        },
        execution_id=exec2.execution_id,
    )
    return exec2


def run_lab0(
    orchestrator: Any,
    *,
    output_dir: Path,
    model: str = PRIMARY_LOCAL_MODEL,
    extra_fixtures: Sequence[RevalidationLabFixture] | None = None,
) -> dict[str, Any]:
    fixtures = build_lab0_fixtures(orchestrator, extra_fixtures=extra_fixtures)
    observations_a = run_arm_a(fixtures, chat_fn_for=chat_fn_for_fixture, model=model)
    observations_b = run_arm_b(fixtures, chat_fn_for=chat_fn_for_fixture, model=model)
    all_observations = observations_a + observations_b
    summary = summarize_lab0_results(all_observations)
    stamp = _utc_stamp()
    jsonl_path = write_observations_jsonl(
        all_observations,
        output_dir / f"revalidation_lab0_{stamp}.jsonl",
    )
    summary_path = output_dir / f"revalidation_lab0_{stamp}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["observations_jsonl"] = str(jsonl_path)
    summary["summary_json"] = str(summary_path)
    return summary


__all__ = [
    "EXECUTION_PROFILE",
    "LAB0_MAX_RETRY",
    "PRIMARY_LOCAL_MODEL",
    "RevalidationLabFixture",
    "RevalidationLabObservation",
    "STRONGER_LOCAL_MODEL",
    "build_lab0_fixtures",
    "chat_fn_for_fixture",
    "run_arm_a",
    "run_arm_b",
    "run_lab0",
    "run_single_evaluation",
    "routing_chat_for_fixture",
    "seed_lab0_handoff_orchestrator",
    "summarize_lab0_results",
    "write_observations_jsonl",
]
