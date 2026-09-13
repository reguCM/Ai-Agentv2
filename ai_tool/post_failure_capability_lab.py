"""Post-Failure Hard Capability Fallback Lab (non-production).

Demonstrates a second defense line after pre-routing:
execution-time hard capability failure -> classify -> local fallback -> retry same task.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from ai_tool.capability_routing_lab import ECHO_PROBE_TOOL, LabTask, default_tool_task
from ai_tool.hard_capability_failure_class import (
    classify_hard_capability_failure,
    is_hard_capability_missing,
)
from ai_tool.tool_calling_capability_bridge import (
    TOOL_CALLING_FALLBACK_CANDIDATES,
    apply_tool_calling_hard_capability_bridge,
    worker_tool_calling_eligibility,
)
from tools.system.model_registry import get_model

EXECUTION_PROFILE_TOOL = "fast_tool"
PRIMARY_WORKER_ID = "deepseek_coder_v2_16b"
REQUIRED_CAPABILITY = "tool_calling"


@dataclass
class PostFailureLabObservation:
    case: str
    primary_model: str
    primary_worker_id: str
    required_capability: str
    precheck_result: str
    primary_execution_attempted: bool
    primary_failure: str | None
    failure_class: str | None
    fallback_candidates: list[str]
    selected_fallback: str | None
    selected_fallback_model: str | None
    fallback_reason: str | None
    final_model: str | None
    final_success: bool
    native_tool_call: bool
    total_latency_ms: float
    attempts: int
    task_case_id: str
    execution_profile: str = EXECUTION_PROFILE_TOOL

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _provider_model(worker_id: str) -> str:
    return str(get_model(worker_id).get("model") or worker_id)


def _fallback_worker_ids(
    *,
    primary_worker_id: str,
    task_ineligible: set[str],
    fallback_candidates: Sequence[str] | None = None,
) -> list[str]:
    ordered: list[str] = []
    for worker_id in fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES:
        token = str(worker_id or "").strip()
        if not token or token in task_ineligible or token == primary_worker_id:
            continue
        if token not in ordered:
            ordered.append(token)
    return ordered


def _select_eligible_fallback(
    *,
    primary_worker_id: str,
    task_ineligible: set[str],
    fallback_candidates: Sequence[str] | None = None,
) -> tuple[str | None, str | None, list[str]]:
    candidates = _fallback_worker_ids(
        primary_worker_id=primary_worker_id,
        task_ineligible=task_ineligible,
        fallback_candidates=fallback_candidates,
    )
    for worker_id in candidates:
        state, _source, reason = worker_tool_calling_eligibility(worker_id)
        if state == "eligible":
            return worker_id, f"first_eligible_fallback:{worker_id}", candidates
    return None, None, candidates


def _execute_tool_task(
    *,
    worker_id: str,
    task: LabTask,
    chat_fn: Callable[..., Any],
) -> tuple[bool, bool, str | None, float]:
    started = time.perf_counter()
    provider_model = _provider_model(worker_id)
    try:
        response = chat_fn(
            model=provider_model,
            messages=[{"role": "user", "content": task.prompt}],
            tools=[ECHO_PROBE_TOOL],
            execution_profile=EXECUTION_PROFILE_TOOL,
        )
    except Exception as exc:  # noqa: BLE001
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return False, False, str(exc), latency_ms

    message = getattr(response, "message", None)
    tool_calls = getattr(message, "tool_calls", None) or []
    names = [
        str(getattr(getattr(call, "function", None), "name", "") or "")
        for call in tool_calls
    ]
    success = task.expected_tool in names
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return success, bool(names), None, latency_ms


def run_case_a_pre_routing(
    task: LabTask,
    *,
    primary_worker_id: str = PRIMARY_WORKER_ID,
    chat_fn: Callable[..., Any],
    fallback_candidates: Sequence[str] | None = None,
) -> PostFailureLabObservation:
    """Production-style pre-routing: skip incompatible primary before execution."""
    started = time.perf_counter()
    primary_model = _provider_model(primary_worker_id)
    bridge = apply_tool_calling_hard_capability_bridge(
        primary_worker_id,
        llm_tools=[ECHO_PROBE_TOOL],
        fallback_candidates=fallback_candidates,
        execution_profile=EXECUTION_PROFILE_TOOL,
    )
    if bridge.capability_gap:
        return PostFailureLabObservation(
            case="A",
            primary_model=primary_model,
            primary_worker_id=primary_worker_id,
            required_capability=REQUIRED_CAPABILITY,
            precheck_result="capability_gap",
            primary_execution_attempted=False,
            primary_failure=bridge.gap_reason,
            failure_class=None,
            fallback_candidates=list(fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES),
            selected_fallback=bridge.selected_worker_id,
            selected_fallback_model=bridge.selected_model,
            fallback_reason=bridge.routing_reason,
            final_model=bridge.selected_model,
            final_success=False,
            native_tool_call=False,
            total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
            attempts=0,
            task_case_id=task.case_id,
        )

    precheck_result = (
        "primary_skipped_precheck"
        if bridge.routing_performed
        else "primary_eligible_precheck"
    )
    selected_worker_id = bridge.selected_worker_id or primary_worker_id
    success, native_tool_call, failure, attempt_latency = _execute_tool_task(
        worker_id=selected_worker_id,
        task=task,
        chat_fn=chat_fn,
    )
    return PostFailureLabObservation(
        case="A",
        primary_model=primary_model,
        primary_worker_id=primary_worker_id,
        required_capability=REQUIRED_CAPABILITY,
        precheck_result=precheck_result,
        primary_execution_attempted=False,
        primary_failure=None,
        failure_class=None,
        fallback_candidates=list(fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES),
        selected_fallback=selected_worker_id if bridge.routing_performed else None,
        selected_fallback_model=bridge.selected_model,
        fallback_reason=bridge.routing_reason,
        final_model=bridge.selected_model,
        final_success=success,
        native_tool_call=native_tool_call,
        total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
        attempts=1,
        task_case_id=task.case_id,
    )


def run_case_b_post_failure_fallback(
    task: LabTask,
    *,
    primary_worker_id: str = PRIMARY_WORKER_ID,
    chat_fn: Callable[..., Any],
    fallback_candidates: Sequence[str] | None = None,
) -> PostFailureLabObservation:
    """Bypass pre-routing, fail on primary, classify, fallback, retry same task."""
    started = time.perf_counter()
    primary_model = _provider_model(primary_worker_id)
    task_ineligible: set[str] = set()
    attempts = 0
    primary_failure: str | None = None
    failure_class: str | None = None
    selected_fallback: str | None = None
    fallback_reason: str | None = None
    candidates: list[str] = []

    attempts += 1
    success, native_tool_call, primary_failure, _primary_latency = _execute_tool_task(
        worker_id=primary_worker_id,
        task=task,
        chat_fn=chat_fn,
    )
    if success:
        return PostFailureLabObservation(
            case="B",
            primary_model=primary_model,
            primary_worker_id=primary_worker_id,
            required_capability=REQUIRED_CAPABILITY,
            precheck_result="bypassed",
            primary_execution_attempted=True,
            primary_failure=None,
            failure_class=None,
            fallback_candidates=list(fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES),
            selected_fallback=None,
            selected_fallback_model=None,
            fallback_reason="primary_succeeded_without_fallback",
            final_model=primary_model,
            final_success=True,
            native_tool_call=native_tool_call,
            total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
            attempts=attempts,
            task_case_id=task.case_id,
        )

    failure_class = classify_hard_capability_failure(
        primary_failure,
        required_capability=REQUIRED_CAPABILITY,
    )
    if not is_hard_capability_missing(failure_class):
        return PostFailureLabObservation(
            case="B",
            primary_model=primary_model,
            primary_worker_id=primary_worker_id,
            required_capability=REQUIRED_CAPABILITY,
            precheck_result="bypassed",
            primary_execution_attempted=True,
            primary_failure=primary_failure,
            failure_class=failure_class,
            fallback_candidates=list(fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES),
            selected_fallback=None,
            selected_fallback_model=None,
            fallback_reason="not_hard_capability_failure",
            final_model=primary_model,
            final_success=False,
            native_tool_call=False,
            total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
            attempts=attempts,
            task_case_id=task.case_id,
        )

    task_ineligible.add(primary_worker_id)
    selected_fallback, fallback_reason, candidates = _select_eligible_fallback(
        primary_worker_id=primary_worker_id,
        task_ineligible=task_ineligible,
        fallback_candidates=fallback_candidates,
    )
    if selected_fallback is None:
        return PostFailureLabObservation(
            case="B",
            primary_model=primary_model,
            primary_worker_id=primary_worker_id,
            required_capability=REQUIRED_CAPABILITY,
            precheck_result="bypassed",
            primary_execution_attempted=True,
            primary_failure=primary_failure,
            failure_class=failure_class,
            fallback_candidates=candidates,
            selected_fallback=None,
            selected_fallback_model=None,
            fallback_reason="no_eligible_fallback_after_hard_failure",
            final_model=primary_model,
            final_success=False,
            native_tool_call=False,
            total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
            attempts=attempts,
            task_case_id=task.case_id,
        )

    attempts += 1
    final_success, native_tool_call, fallback_failure, _fallback_latency = _execute_tool_task(
        worker_id=selected_fallback,
        task=task,
        chat_fn=chat_fn,
    )
    return PostFailureLabObservation(
        case="B",
        primary_model=primary_model,
        primary_worker_id=primary_worker_id,
        required_capability=REQUIRED_CAPABILITY,
        precheck_result="bypassed",
        primary_execution_attempted=True,
        primary_failure=primary_failure,
        failure_class=failure_class,
        fallback_candidates=candidates,
        selected_fallback=selected_fallback,
        selected_fallback_model=_provider_model(selected_fallback),
        fallback_reason=fallback_reason,
        final_model=_provider_model(selected_fallback),
        final_success=final_success,
        native_tool_call=native_tool_call,
        total_latency_ms=round((time.perf_counter() - started) * 1000, 1),
        attempts=attempts,
        task_case_id=task.case_id,
    )


def summarize_post_failure_lab(
    case_a: PostFailureLabObservation,
    case_b: PostFailureLabObservation,
) -> dict[str, Any]:
    return {
        "case_a_final_success": case_a.final_success,
        "case_b_final_success": case_b.final_success,
        "case_a_primary_execution_attempted": case_a.primary_execution_attempted,
        "case_b_primary_execution_attempted": case_b.primary_execution_attempted,
        "case_b_failure_class": case_b.failure_class,
        "case_a_selected_fallback": case_a.selected_fallback,
        "case_b_selected_fallback": case_b.selected_fallback,
        "case_a_total_latency_ms": case_a.total_latency_ms,
        "case_b_total_latency_ms": case_b.total_latency_ms,
        "case_a_attempts": case_a.attempts,
        "case_b_attempts": case_b.attempts,
        "pre_routing_avoids_primary_failure": (
            not case_a.primary_execution_attempted and case_a.final_success
        ),
        "post_failure_fallback_demonstrated": (
            case_b.primary_execution_attempted
            and case_b.failure_class == "hard_capability_missing"
            and case_b.final_success
        ),
        "case_a_lower_attempt_count": case_a.attempts < case_b.attempts,
        "both_paths_succeed": case_a.final_success and case_b.final_success,
    }


def write_observations_jsonl(
    observations: Sequence[PostFailureLabObservation],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in observations:
            handle.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
    return path


def run_post_failure_capability_lab(
    *,
    output_dir: Path,
    primary_worker_id: str = PRIMARY_WORKER_ID,
    chat_fn: Callable[..., Any] | None = None,
    fallback_candidates: Sequence[str] | None = None,
) -> dict[str, Any]:
    if chat_fn is None:
        from tools.system.llm import chat as default_chat

        chat_fn = default_chat

    task = default_tool_task()
    case_a = run_case_a_pre_routing(
        task,
        primary_worker_id=primary_worker_id,
        chat_fn=chat_fn,
        fallback_candidates=fallback_candidates,
    )
    case_b = run_case_b_post_failure_fallback(
        task,
        primary_worker_id=primary_worker_id,
        chat_fn=chat_fn,
        fallback_candidates=fallback_candidates,
    )
    summary = summarize_post_failure_lab(case_a, case_b)
    stamp = _utc_stamp()
    jsonl_path = write_observations_jsonl(
        [case_a, case_b],
        output_dir / f"post_failure_capability_lab_{stamp}.jsonl",
    )
    payload = {
        "task": asdict(task),
        "primary_worker_id": primary_worker_id,
        "required_capability": REQUIRED_CAPABILITY,
        "summary": summary,
        "observations": [case_a.as_dict(), case_b.as_dict()],
        "observations_jsonl": str(jsonl_path),
    }
    summary_path = output_dir / f"post_failure_capability_lab_{stamp}_summary.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["summary_json"] = str(summary_path)
    return payload


__all__ = [
    "PostFailureLabObservation",
    "PRIMARY_WORKER_ID",
    "REQUIRED_CAPABILITY",
    "run_case_a_pre_routing",
    "run_case_b_post_failure_fallback",
    "run_post_failure_capability_lab",
    "summarize_post_failure_lab",
]
