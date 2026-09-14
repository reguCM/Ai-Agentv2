"""Local Agent の 1 ターン。agent.py は import しない。

使うもの:
- tools.system.llm.chat（Ollama）
- registry visibility=agent Tool
- agent_tool_gate（Chat 専用 trust。本番 trust は書き換えない）
- Experimental bind/diff/select は表示用。全記憶は LLM に渡さない。
"""
from __future__ import annotations

import importlib
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    ollama_tools_for_llm,
    registry_index,
)
from ai_tool.agent_integration.experimental_exposure import load_registry_tools
from ai_tool.agent_integration.trial import normalize_arguments
from ai_tool.chat_interface.chat_session import (
    append_session_message,
    development_state_from_session,
    research_store_from_session,
    save_session,
)
from ai_tool.chat_interface.activity import new_correlation_id, stamp_events
from ai_tool.chat_interface.activity_status import (
    ActivityStatus,
    begin_turn,
    finish_turn,
    response_is_current,
    update_activity,
)
from ai_tool.chat_interface.classify import classify_request, intent_of, looks_like_followup
from ai_tool.chat_interface.development_job import maybe_record_job
from ai_tool.chat_interface.execution_case import attach_or_open_case, record_turn
from ai_tool.chat_interface.events import (
    event,
    mission_ui_summary,
    now_iso,
    pipeline_steps,
    public_status_lines,
    runtime_ui_summary,
    summarize_tool_result,
)
from ai_tool.chat_interface.llm_errors import classify_llm_error
from ai_tool.chat_interface.concept_resolution import (
    apply_concept_guidance_to_requirements,
    detect_unknown_concept,
)
from ai_tool.chat_interface.local_review import (
    build_review_input,
    call_local_reviewer,
    validate_review,
)
from ai_tool.chat_interface.requirement_decomposition import (
    RequirementDecomposition,
    RequirementStatus,
    decompose_requirements,
)
from ai_tool.chat_interface.task_orchestration import (
    AGENT_CORE_PROMPT,
    ChatTaskOrchestrator,
    has_creation_intent,
    is_agent_task,
)
from ai_tool.chat_interface.boundary_grill import (
    apply_boundary_grill_answer,
    boundary_grill_open_dimensions,
    boundary_grill_runtime_connected,
    launch_boundary_grill,
    reroute_after_boundary_grill_answer,
    restore_orchestrator_from_boundary_grill,
    should_launch_boundary_grill,
)
from ai_tool.chat_interface.decision_change_gate import (
    OPTION_CONFIRM_CHANGE,
    OPTION_DEFER_CHANGE,
    OPTION_KEEP_PRIOR,
    interpret_decision_change_answer,
    launch_decision_change_confirmation,
    prepare_boundary_grill_answer,
)
from ai_tool.chat_interface.gap_resolution_router import (
    CapabilityId,
    apply_regression_continuation_bridge,
    observe_gap_resolution_at_execution_end,
    should_persist_goal_continuation_resume,
    build_goal_continuation_resume,
)
from ai_tool.chat_interface.goal_continuation_progress import (
    capture_gap_snapshot,
    observe_goal_continuation_progress,
)
from ai_tool.chat_interface.progress_classification_shadow import (
    ProgressShadowTracker,
    snapshot_from_orchestrator,
)
from ai_tool.chat_interface.progress_classification_v0 import classify_progress_transition
from ai_tool.chat_interface.agent_stop_control import (
    finalize_exit_answer,
    is_resumable_pause_stop,
    should_skip_agent_llm_after_stop,
    should_system_fast_exit_after_stop,
    system_exit_answer,
)
from ai_tool.chat_interface.semantic_stagnation_warning import (
    SemanticStagnationWarningTracker,
    active_semantic_warnings,
    is_semantic_fuse_stop,
    resolve_actual_stop_reason,
    semantic_warning_enabled_from_pipeline,
    state_snapshot_key,
)
from ai_tool.pipeline_observations import PipelineBudgetExceeded, PipelineObserver
from tools.ai.task_runtime import ProgressState
from ai_tool.chat_interface.goal_continuation_resume import (
    GoalContinuationRestoreError,
    apply_continuation_winner,
    goal_continuation_context_from_packet,
    is_explicit_continuation_trigger,
    restore_orchestrator_from_goal_continuation,
    validate_goal_continuation_packet,
)
from ai_tool.chat_interface.goal_completion_gate import (
    format_goal_completion_judgment,
    interpret_goal_completion_answer,
)
from ai_tool.mission_memory.chat_persist import (
    bind_execution_identity,
    persist_chat_execution,
)
from ai_tool.mission_memory.clarifications import restore_mission_clarifications
from ai_tool.production_handoff_bridge import (
    apply_production_grill_human_answer,
    assess_production_handoff_readiness,
    is_explicit_production_handoff_trigger,
    mark_session_production_handoff_completed,
    orchestrator_has_goal_handoff_seed,
    prepare_production_handoff_orchestrator,
    run_production_handoff_pipeline,
    run_production_spec_handoff_pipeline,
    run_production_grill_phase1,
    session_has_production_handoff,
)
from ai_tool.dev_skill_pipeline import validate_handoff_packet
from ai_tool.goal_handoff_runtime_bridge import (
    prepare_orchestrator_from_handoff,
    restore_orchestrator_from_runtime_snapshot,
)
from ai_tool.goal_handoff_source_binding import validate_handoff_source_binding
from ai_tool.production_meaning_context import MeaningContextError, build_meaning_context_v0
from ai_tool.production_run_contract import (
    build_production_run_contract,
    validate_production_run_contract,
)
from ai_tool.mission_memory.paths import MissionMemoryError
from ai_tool.mission_memory.ids import new_mission_id
from ai_tool.mission_memory.store import MissionMemoryStore
from ai_tool.mission_memory.validate import schema_version
from ai_tool.chat_interface.requirement_resolution import (
    PHASE_REQUIREMENTS_RESOLVED,
    RequirementResolutionBundle,
    implementation_entry_requested,
    load_bundle_from_mission,
    merge_mission_requirement_fields,
    mission_blocks_implementation_entry,
    prepare_implementation_entry_bundle,
    project_to_runtime_adoption,
    requirements_block_implementation_entry,
    sync_canonical_requirement_projection,
)
from ai_tool.chat_interface.requirement_resolution_grill import (
    apply_requirement_resolution_grill_answer,
    launch_requirement_resolution_grill,
)
from ai_tool.chat_interface.semantic_revalidation_gate import (
    blocks_implementation_entry,
    build_derived_spec_for_implementation_entry,
    preview_implementation_adoption,
    resolved_context_from_handoff,
    run_implementation_semantic_revalidation,
    semantic_revalidation_blocked_answer,
    should_run_semantic_revalidation_gate,
)
from ai_tool.requirement_semantic_revalidation import SemanticRevalidationResult
from ai_tool.help.api import format_help_for_chat, handle_h as help_handle_h
from ai_tool.experimental.development_assistance.development_session import apply_requirement
from ai_tool.experimental.development_assistance.memory_slice import compare_llm_payloads
from ai_tool.experimental.development_assistance.pointer_resolution import classify_pointer
from tools.system.agent_tool_gate import authorize_tool_execution, blocked_result, load_trust_store
from tools.system.config import get_llm_profile, get_pipeline
from tools.ai.sandbox_workspace import resolve_configured_sandbox_parent
from tools.system.execution_identity import PROJECT_AGENT, log_tool_call, log_tool_result
from tools.system.execution_profile import agent_turn_phase_profile
from tools.system.llm import chat as ollama_chat
from tools.system.model_registry import resolve_provider_model_name
from tools.system.network.web_evidence import enrich_web_tool_result
from ai_tool.chat_interface.workspace_read_bridge import (
    prepare_tool_result_for_llm,
    runtime_initial_read_arguments,
)
from tools.system.tool_result_contract import normalize_tool_result

ChatFn = Callable[..., Any]
DEVELOPMENT_WORKTREE = Path(__file__).resolve().parents[2]


def _resolve_runtime_model_name(model: str | None, session: Mapping[str, Any]) -> str:
    """Accept either a configured profile id or an Ollama model name."""
    requested = str(model or session.get("model") or "").strip() or None
    return resolve_provider_model_name(requested)


def _new_timing_breakdown() -> dict[str, Any]:
    return {
        "requirement_decomposition_ms": 0,
        "agent_initial_llm_ms": 0,
        "tool_execution_ms": 0,
        "agent_post_tool_llm_ms": 0,
        "final_synthesis_llm_ms": 0,
        "local_review_llm_ms": 0,
        "total_turn_ms": 0,
        "llm_calls": [],
        "tool_executions": [],
    }


def _timed_llm_call(
    chat_fn: ChatFn,
    phase: str,
    timing: dict[str, Any],
    **kwargs: Any,
) -> Any:
    started_at = now_iso()
    started = time.perf_counter()
    response = None
    error = None
    execution_profile = kwargs.get("execution_profile") or agent_turn_phase_profile(phase)
    kwargs = dict(kwargs)
    kwargs.setdefault("execution_profile", execution_profile)
    try:
        response = chat_fn(**kwargs)
        return response
    except Exception as exc:  # timing must not change exception behavior
        error = type(exc).__name__
        raise
    finally:
        finished_at = now_iso()
        elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
        message = getattr(response, "message", None)
        content = str(getattr(message, "content", None) or "")
        tool_calls = getattr(message, "tool_calls", None) or []
        timing[f"{phase}_ms"] = int(timing.get(f"{phase}_ms") or 0) + elapsed_ms
        timing["llm_calls"].append(
            {
                "phase": phase.removesuffix("_ms"),
                "request_started_at": started_at,
                # Ollama chat is non-streaming here; first/last response are
                # observable only when the complete response is returned.
                "first_response_at": finished_at if response is not None else None,
                "last_response_at": finished_at if response is not None else None,
                "request_finished_at": finished_at,
                "elapsed_ms": elapsed_ms,
                "model": kwargs.get("model"),
                "execution_profile": execution_profile,
                "tool_calls_returned": len(tool_calls),
                "response_length": len(content),
                "thinking_length": len(str(getattr(message, "thinking", None) or "")),
                "error": error,
            }
        )


class LoopStopReason(str, Enum):
    TOOL_HARD_LIMIT = "TOOL_HARD_LIMIT"
    STAGNATION_LIMIT = "STAGNATION_LIMIT"
    SAME_FAILURE_LIMIT = "SAME_FAILURE_LIMIT"
    NO_EVIDENCE_LIMIT = "NO_EVIDENCE_LIMIT"
    USER_CANCELLED = "USER_CANCELLED"
    TIMEOUT = "TIMEOUT"
    PIPELINE_BUDGET_EXCEEDED = "PIPELINE_BUDGET_EXCEEDED"
    LLM_EMPTY_RESPONSE = "LLM_EMPTY_RESPONSE"
    LLM_RESPONSE_ERROR = "LLM_RESPONSE_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    HUMAN_GRILL = "HUMAN_GRILL"
    GOAL_COMPLETION_HUMAN = "GOAL_COMPLETION_HUMAN"
    GOAL_CONTINUATION_REGRESSION = "GOAL_CONTINUATION_REGRESSION"
    GOAL_INCOMPLETE_OPEN_WORK = "GOAL_INCOMPLETE_OPEN_WORK"
    GOAL_INCOMPLETE_BLOCKED = "GOAL_INCOMPLETE_BLOCKED"
    GOAL_INCOMPLETE_CONTINUATION = "GOAL_INCOMPLETE_CONTINUATION"
    GOAL_INCOMPLETE_REPLAN = "GOAL_INCOMPLETE_REPLAN"
    PREMISE_REVALIDATION_EXECUTION_BLOCKED = "PREMISE_REVALIDATION_EXECUTION_BLOCKED"
    TASK_CHANGE_PROPAGATION_NON_CONVERGED = "TASK_CHANGE_PROPAGATION_NON_CONVERGED"
    HARD_CAPABILITY_GAP = "HARD_CAPABILITY_GAP"
    COMPLETED = "COMPLETED"


_INCOMPLETE_GOAL_STOP_REASONS = {
    "blocked": LoopStopReason.GOAL_INCOMPLETE_BLOCKED,
    "incomplete": LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK,
    "continuation": LoopStopReason.GOAL_INCOMPLETE_CONTINUATION,
    "replan": LoopStopReason.GOAL_INCOMPLETE_REPLAN,
}
_INCOMPLETE_GOAL_STOP_SET = frozenset(_INCOMPLETE_GOAL_STOP_REASONS.values())
def _incomplete_goal_stop_reason(orchestrator: ChatTaskOrchestrator) -> LoopStopReason | None:
    outcome = orchestrator.incomplete_goal_terminal_outcome()
    if not outcome:
        return None
    return _INCOMPLETE_GOAL_STOP_REASONS.get(outcome, LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK)


@dataclass
class LoopCounters:
    stagnation_limit: int
    same_failure_limit: int
    no_evidence_limit: int
    configured_tool_limit: int | None = None
    total_tool_calls: int = 0
    stagnation_count: int = 0
    same_failure_count: int = 0
    no_evidence_count: int = 0
    recovery_count: int = 0
    _last_signature: str | None = None
    _last_failure_signature: str | None = None

    def observe(self, *, signature: str, status: str, evidence_gain: bool) -> None:
        self.total_tool_calls += 1
        failed = status == "failure"
        failure_signature = signature if failed else None
        self.same_failure_count = (
            self.same_failure_count + 1
            if failure_signature and failure_signature == self._last_failure_signature
            else (1 if failure_signature else 0)
        )
        self.no_evidence_count = 0 if evidence_gain else self.no_evidence_count + 1
        repeated_without_evidence = not evidence_gain and signature == self._last_signature
        if evidence_gain:
            self.stagnation_count = 0
        elif repeated_without_evidence:
            self.stagnation_count += 1
        # A different Action without objective progress neither increments nor
        # resets stagnation. no_evidence_count still tracks that condition.
        self._last_signature = signature
        self._last_failure_signature = failure_signature

    def stop_reason(self) -> LoopStopReason | None:
        if self.same_failure_count >= self.same_failure_limit:
            return LoopStopReason.SAME_FAILURE_LIMIT
        if self.stagnation_count >= self.stagnation_limit:
            return LoopStopReason.STAGNATION_LIMIT
        if self.no_evidence_count >= self.no_evidence_limit:
            return LoopStopReason.NO_EVIDENCE_LIMIT
        return None

    def snapshot(self) -> dict[str, int]:
        return {
            "total_tool_calls": self.total_tool_calls,
            "stagnation_count": self.stagnation_count,
            "same_failure_count": self.same_failure_count,
            "no_evidence_count": self.no_evidence_count,
            "recovery_count": self.recovery_count,
            "configured_tool_limit": self.configured_tool_limit,
        }

# Security/trust bootstrap only. UI visibility and LLM exposure are derived
# from Registry; adding a visible Tool must not silently auto-allow execution.
CHAT_TRUST_BOOTSTRAP_ALLOWLIST = (
    "get_gpu_status",
    "get_gpu_processes",
    "cpu_status",
    "get_cpu_status",
    "get_system_summary",
    "search_web",
    "read_url_text",
)
# Backward-compatible name for callers/tests; no longer a visibility source.
AGENT_VISIBLE_DEFAULT = CHAT_TRUST_BOOTSTRAP_ALLOWLIST

SYSTEM_PROMPT = """
あなたはローカル環境の Local Agent です。日本語で簡潔に答えてください。

使える事実は次だけです。
- ユーザー要求
- 会話の直近履歴
- Tool 実行結果

公開 Toolは、このリクエストと同時に渡されるRegistry由来のTool schemaを正本とする。

ルール:
- ユーザーが観測を求めたら、推測せず Tool を使う。
- Web の事実は Tool 結果に無い数値を補完しない。
- ファイル作成はしない。新しい Tool の Registry 登録はしない。
- 全 Memory を探して整理するな。渡されていない ResearchRecord は使うな。
""".strip()


def agent_visible_capabilities(
    registry_tools: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return display metadata for exactly the Registry agent-visible set."""
    entries = registry_tools if registry_tools is not None else load_registry_tools()
    return [
        {
            "name": str(entry["name"]),
            "description": str(entry.get("description") or ""),
            "risk": entry.get("risk"),
            "observation_source": entry.get("observation_source"),
        }
        for entry in sorted(entries, key=lambda item: str(item.get("name") or ""))
        if entry.get("visibility") == "agent" and entry.get("name")
    ]


def chat_trust_path(session_id: str) -> Path:
    path = Path(__file__).resolve().parents[2] / "runs" / "chat_ui" / "trust" / f"{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        store = load_trust_store()
        store["auto_allow"] = sorted(set(CHAT_TRUST_BOOTSTRAP_ALLOWLIST))
        store["note"] = (
            "Chat UI session trust. Does not replace registry/agent_tool_trust.json. "
            "Human already sent the chat message."
        )
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _pipeline_budget_stop_reason(
    pipeline_observer: PipelineObserver | None,
) -> LoopStopReason | None:
    if pipeline_observer is None:
        return None
    try:
        pipeline_observer.check_budget()
    except PipelineBudgetExceeded:
        return LoopStopReason.PIPELINE_BUDGET_EXCEEDED
    return None


def _execute_agent_tool(
    tool_name: str,
    arguments: Any,
    *,
    trust_path: Path,
    case_id: str | None = None,
    sandbox_session: Any = None,
) -> dict[str, Any]:
    args = normalize_arguments(arguments)
    reg = registry_index()
    if tool_name not in reg:
        return {"ok": False, "error": f"RegistryにToolが登録されていません: {tool_name}"}
    auth = authorize_tool_execution(
        tool_name,
        args,
        ask_confirm=lambda _n, _a: "y",
        store_path=trust_path,
    )
    extra = {"agent_tool_gate": auth, "chat_ui": True}
    if case_id:
        extra["case_id"] = case_id
    if not auth.get("allowed"):
        denied = blocked_result(tool_name, reason=str(auth.get("decision") or "deny"), arguments=args)
        log_tool_call(
            execution_actor=PROJECT_AGENT,
            tool_name=tool_name,
            arguments=args,
            extra={**extra, "blocked": True},
        )
        return denied
    log_tool_call(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        arguments=args,
        extra=extra,
    )
    entry = reg[tool_name]
    module = importlib.import_module(str(entry["module"]))
    function = getattr(module, str(entry["function"]))
    try:
        if tool_name in {"create_file", "edit_file"}:
            if sandbox_session is None:
                result = {
                    "ok": False,
                    "status": "failure",
                    "error": {
                        "code": "sandbox_session_required",
                        "message": "Runtime-owned Dedicated Sandbox Session is required.",
                    },
                    "warnings": [],
                }
            else:
                result = function(**args, sandbox_session=sandbox_session)
        else:
            result = function(**args)
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(result, dict):
        result = {"result": result}
    try:
        result = enrich_web_tool_result(tool_name, result)
    except Exception:
        pass
    log_tool_result(
        execution_actor=PROJECT_AGENT,
        tool_name=tool_name,
        result=result,
        extra=extra,
    )
    return result


def _memory_overlay(user_text: str, session: dict[str, Any]) -> dict[str, Any]:
    store = research_store_from_session(session)
    state = development_state_from_session(session)
    pointer = classify_pointer(user_text, store=store, session=state.as_session_dict())
    applied = apply_requirement(state, user_text, store)
    bound_id = str(state.last_research_id or pointer.bound_research_id or "")
    facet_ids = list(state.facets.keys())
    cmp_ = compare_llm_payloads(
        store,
        bound_research_id=bound_id,
        session_facet_ids=facet_ids,
        missing_facet_ids=[],
    )
    session["experimental_session"] = state.as_session_dict()
    return {
        "followup": looks_like_followup(user_text),
        "pointer": pointer.to_dict(),
        "applied": {
            "changed": applied.get("changed"),
            "missing": applied.get("missing"),
            "reusable": applied.get("reusable"),
            "copied_old_python_evidence": applied.get("copied_old_python_evidence"),
        },
        "research_record_id": bound_id or None,
        "research_saved": False,
        "all_memory_facet_count": cmp_["all_memory_facet_count"],
        "selected_facets": list(cmp_["selected_ids"]),
        "llm_facet_count": cmp_["llm_slice_facet_count"],
        "dump_all_passed_to_llm": False,
        "copied_312_evidence_to_313": bool(applied.get("copied_old_python_evidence")),
        "note": (
            "ResearchRecord は Agent Chat では保存していない。"
            "Chat → run_standard_workflow / ResearchStore.add_from_run は NOT CONNECTED。"
            "bind/diff/select は Experimental Adapter の表示。全記憶は LLM に渡していない。"
        ),
    }


def _spec_proposal_turn(
    user_text: str,
    *,
    chat_fn: ChatFn,
    model: str,
    source: str,
    route: str,
    session_id: str | None = None,
    development_job_id: str | None = None,
    correlation_id: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    from ai_tool.spec_proposal.propose import propose_specification

    events = [
        event("local_agent_call", status="started", route=route, model=model),
        event("request", text=user_text, route=route),
        event("route", route=route, executor="local_agent"),
    ]
    record = propose_specification(
        user_text,
        chat_fn=chat_fn,
        model=model,
        source=source,
        requested_by="user",
        correlation_id=correlation_id,
        session_id=session_id,
        development_job_id=development_job_id,
        case_id=case_id,
    )
    events.extend(record.get("events") or [])
    human_items = record.get("human_confirmation_required") or []
    parse_ok = record.get("parse_status") == "ok"
    awaiting = True if route == "tool_creation" else bool(human_items) or not parse_ok
    result = {
        "route": route,
        "answer": str(record.get("answer") or ""),
        "events": events,
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "awaiting_human_review": awaiting,
        "registry_write": False,
        "proposal": {
            "proposal_id": record.get("proposal_id"),
            "request_id": record.get("request_id"),
            "version": record.get("version"),
            "parse_status": record.get("parse_status"),
            "target_request": user_text,
        },
        "spec_proposal": record,
        "spec_error": record.get("error"),
        "executor": "local_agent",
        "cursor_connected": False,
    }
    if record.get("is_error"):
        result["is_error"] = True
        result["error"] = record.get("error")
        result["error_kind"] = record.get("error_kind")
        result["user_error"] = record.get("user_error")
        result["awaiting_human_review"] = False if route == "tool_creation" and record.get("is_error") else awaiting
    return result


def _record_mission_memory(
    orchestrator: ChatTaskOrchestrator | None,
    stop_reason: LoopStopReason | None,
    *,
    determined: bool,
    answer: str,
    correlation_id: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if orchestrator is None:
        return None
    reason = stop_reason.value if stop_reason is not None else "UNKNOWN"
    try:
        recorded = persist_chat_execution(
            orchestrator,
            stop_reason=reason,
            determined=determined,
            answer=answer,
            correlation_id=correlation_id,
        )
        events.append(
            event(
                "mission_memory",
                status="saved",
                mission_id=recorded.get("mission_id"),
                execution_id=recorded.get("execution_id"),
            )
        )
        return recorded
    except MissionMemoryError as exc:
        events.append(
            event(
                "mission_memory",
                status="failed",
                code=exc.code,
                message=str(exc),
            )
        )
        return {"ok": False, "code": exc.code, "message": str(exc)}


def _finalize_semantic_warning_tracker(
    tracker: SemanticStagnationWarningTracker | None,
    *,
    actual_stop_reason: LoopStopReason | None,
    orchestrator: ChatTaskOrchestrator | None,
) -> dict[str, Any] | None:
    if tracker is None:
        return None
    tracker.finalize(
        actual_stop_reason=actual_stop_reason,
        orchestrator=orchestrator,
    )
    return tracker.as_dict()


def _build_system_exit_turn_result(
    *,
    stop_reason: LoopStopReason | None,
    answer: str,
    events: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    orchestrator: ChatTaskOrchestrator | None,
    counters: LoopCounters,
    lifecycle: dict[str, Any],
    runtime_status_report: dict[str, Any] | None,
    memory: dict[str, Any],
    recorded: dict[str, Any] | None,
    semantic_warning_tracker: SemanticStagnationWarningTracker | None,
    progress_shadow_tracker: ProgressShadowTracker | None,
    cancelled: bool = False,
    error: str | None = None,
    classified: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist and return without post-stop routers (gap/help/recovery/completion)."""
    web_used = any(
        e["name"] in {"search_web", "read_url_text"} for e in executions
    )
    confirmed_gaps = (
        [
            item
            for item in orchestrator.runtime.tool_gaps.values()
            if item.status == "confirmed" and item.requires_human_approval
        ]
        if orchestrator is not None
        else []
    )
    awaiting_human_grill = bool(
        orchestrator is not None and orchestrator.needs_human_grill()
    )
    awaiting_goal_completion_human = bool(
        orchestrator is not None and orchestrator.needs_goal_completion_human()
    )
    result: dict[str, Any] = {
        "route": "chat",
        "answer": answer,
        "events": events,
        "tool_used": bool(executions),
        "tools": executions,
        "web_search": web_used,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": orchestrator.snapshot() if orchestrator else None,
        "final_synthesis": None,
        "final_llm_lifecycle": lifecycle,
        "runtime_status_report": runtime_status_report,
        "loop_counters": counters.snapshot(),
        "answer_gate": None,
        "gap_resolution": None,
        "goal_continuation_resume": None,
        "awaiting_goal_continuation": False,
        "goal_continuation_help_escalation": False,
        "awaiting_boundary_grill": False,
        "boundary_grill": None,
        "boundary_grill_state": None,
        "awaiting_human_review": bool(confirmed_gaps),
        "awaiting_human_grill": awaiting_human_grill,
        "awaiting_goal_completion_human": awaiting_goal_completion_human,
        "conversation_grill": (
            orchestrator.conversation_grill_record()
            if awaiting_human_grill and orchestrator is not None
            else None
        ),
        "goal_completion_human": (
            orchestrator.goal_completion_human_record()
            if awaiting_goal_completion_human and orchestrator is not None
            else None
        ),
        "goal_completion_resume": None,
        "tool_gap_proposals": [asdict(item) for item in confirmed_gaps],
        "mission_memory": recorded,
        "system_fast_exit": True,
        "progress_classification_shadow": (
            progress_shadow_tracker.finalize_and_as_dict(
                actual_stop_reason=stop_reason,
                orchestrator=orchestrator,
            )
            if progress_shadow_tracker is not None
            else None
        ),
        "semantic_stagnation_warning": _finalize_semantic_warning_tracker(
            semantic_warning_tracker,
            actual_stop_reason=stop_reason,
            orchestrator=orchestrator,
        ),
    }
    if cancelled:
        result["cancelled"] = True
    if error:
        result["error"] = error
        result["is_error"] = True
        if classified is not None:
            result["error_kind"] = classified.get("kind")
            result["user_error"] = classified.get("user_message")
    if is_resumable_pause_stop(stop_reason) and awaiting_goal_completion_human:
        if orchestrator is not None:
            resume = orchestrator.goal_completion_resume_state()
            if recorded:
                resume["evidence_refs"] = list(recorded.get("evidence_refs") or [])
                resume["prior_execution_id"] = recorded.get("execution_id")
            result["goal_completion_resume"] = resume
    return result


def _runtime_status_report(
    reason: LoopStopReason,
    counters: LoopCounters,
    orchestrator: ChatTaskOrchestrator | None,
) -> dict[str, Any]:
    task = orchestrator.task if orchestrator is not None else None
    goal = (
        orchestrator.runtime.goals.get(orchestrator.current_goal_id)
        if orchestrator is not None
        else None
    )
    evidence_count = len(orchestrator.runtime.evidence) if orchestrator is not None else 0
    state = "CANCELLED" if reason is LoopStopReason.USER_CANCELLED else "IN_PROGRESS"
    if reason is LoopStopReason.HUMAN_GRILL:
        state = "AWAITING_USER"
    elif reason is LoopStopReason.GOAL_COMPLETION_HUMAN:
        state = "AWAITING_USER"
    elif reason in {
        LoopStopReason.TOOL_HARD_LIMIT,
        LoopStopReason.STAGNATION_LIMIT,
        LoopStopReason.SAME_FAILURE_LIMIT,
        LoopStopReason.NO_EVIDENCE_LIMIT,
        LoopStopReason.PIPELINE_BUDGET_EXCEEDED,
        LoopStopReason.APPROVAL_REQUIRED,
        LoopStopReason.GOAL_CONTINUATION_REGRESSION,
        LoopStopReason.GOAL_INCOMPLETE_BLOCKED,
        LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK,
        LoopStopReason.GOAL_INCOMPLETE_CONTINUATION,
        LoopStopReason.GOAL_INCOMPLETE_REPLAN,
        LoopStopReason.TASK_CHANGE_PROPAGATION_NON_CONVERGED,
        LoopStopReason.HARD_CAPABILITY_GAP,
    }:
        state = "BLOCKED"
    if reason in {LoopStopReason.RUNTIME_ERROR, LoopStopReason.LLM_RESPONSE_ERROR}:
        state = "FAILED"
    next_actions = (
        ["人間が検索対象の同一性を指定する"]
        if reason is LoopStopReason.HUMAN_GRILL
        else ["HumanがGoal Completionを判断する"]
        if reason is LoopStopReason.GOAL_COMPLETION_HUMAN
        else ["不足Capabilityを追加するかHuman Approvalで判断"]
        if reason is LoopStopReason.APPROVAL_REQUIRED
        else ["未完了Taskを実行する", "継続", "Replan"]
        if reason
        in {
            LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK,
            LoopStopReason.GOAL_INCOMPLETE_CONTINUATION,
        }
        else ["Recoveryを継続", "Replan", "上位LLMへ相談"]
        if reason is LoopStopReason.GOAL_INCOMPLETE_REPLAN
        else ["不足Capabilityを確認するかHuman Approvalで判断"]
        if reason is LoopStopReason.GOAL_INCOMPLETE_BLOCKED
        else ["tool_calling 対応 Local Worker を追加するか別経路を指定する"]
        if reason is LoopStopReason.HARD_CAPABILITY_GAP
        else ["Recoveryを継続", "Replan", "上位LLMへ相談"]
        if reason is not LoopStopReason.GOAL_CONTINUATION_REGRESSION
        else [
            "Replanが利用できないため自動継続を停止しました",
            "上位LLMへ相談",
            "Humanへ判断を委ねる",
            "別の方針を指定する",
        ]
    )
    unresolved = [task.title] if task and task.status != "complete" else []
    markdown = "\n".join(
        [
            f"処理状態: {state}",
            "",
            f"停止理由: {reason.value}",
            "",
            f"現在のGoal: {goal.title if goal else '不明'}",
            f"Current Task: {task.title if task else '不明'}",
            f"進捗: {task.progress_state if task and task.progress_state else 'unknown'}",
            f"取得済みEvidence: {evidence_count}",
            f"Tool Call: {counters.total_tool_calls}",
            f"Stagnation: {counters.stagnation_count}",
            f"Recovery: {counters.recovery_count}",
            "未解決事項: " + (", ".join(unresolved) or "なし"),
            "次に可能な対応:",
            *[f"- {item}" for item in next_actions],
        ]
    )
    return {
        "status": state,
        "reason_code": reason.value,
        "current_goal": goal.title if goal else None,
        "current_task": task.title if task else None,
        "progress": task.progress_state if task else None,
        "evidence_count": evidence_count,
        "total_tool_calls": counters.total_tool_calls,
        "stagnation_count": counters.stagnation_count,
        "same_failure_count": counters.same_failure_count,
        "no_evidence_count": counters.no_evidence_count,
        "recovery_count": counters.recovery_count,
        "configured_tool_limit": counters.configured_tool_limit,
        "unresolved_items": unresolved,
        "next_actions": next_actions,
        "markdown": markdown,
    }


def _run_finalization_only(
    *,
    chat_fn: ChatFn,
    model: str,
    messages: list[dict[str, Any]],
    runtime_status_report: Mapping[str, Any],
    timing: dict[str, Any],
) -> Any:
    """Generate the normal tool-free final status from current runtime facts."""
    finalization_messages = [
        *messages,
        {
            "role": "system",
            "content": (
                "Tool execution has stopped. Do not claim the Task or Goal is complete. "
                "Return a concise human-readable status using these observed facts:\n"
                + str(runtime_status_report.get("markdown") or "")
            ),
        },
    ]
    return _timed_llm_call(
        chat_fn,
        "final_synthesis_llm",
        timing,
        model=model,
        messages=finalization_messages,
        tools=[],
    )


def _chat_turn(
    user_text: str,
    session: dict[str, Any],
    *,
    chat_fn: ChatFn,
    model: str,
    memory: dict[str, Any],
    case_id: str | None = None,
    correlation_id: str,
    orchestrator: ChatTaskOrchestrator | None = None,
    timing: dict[str, Any] | None = None,
    local_review_enabled: bool = False,
    review_chat_fn: ChatFn | None = None,
    grill_answer: str | None = None,
    goal_continuation_context: dict[str, Any] | None = None,
    pipeline_observer: PipelineObserver | None = None,
    max_tool_calls_this_turn: int | None = None,
) -> dict[str, Any]:
    timing = timing if timing is not None else _new_timing_breakdown()
    events = [
        event("local_agent_call", status="started", route="chat", model=model, session_id=session.get("session_id")),
        event("request", text=user_text, route="chat"),
        event("route", route="chat", executor="local_agent"),
        event(
            "memory_select",
            selected_facets=memory.get("selected_facets") or [],
            all_memory_facet_count=memory.get("all_memory_facet_count") or 0,
            llm_facet_count=memory.get("llm_facet_count") or 0,
            dump_all_passed_to_llm=False,
            research_record_id=memory.get("research_record_id"),
            research_saved=False,
            pointer=(memory.get("pointer") or {}).get("status"),
        ),
    ]
    if goal_continuation_context:
        events.append(
            event(
                "goal_continuation_restored",
                mission_id=goal_continuation_context.get("mission_id"),
                prior_execution_id=goal_continuation_context.get("prior_execution_id"),
                prior_correlation_id=goal_continuation_context.get("prior_correlation_id"),
                winner=goal_continuation_context.get("winner"),
                gap_kind=goal_continuation_context.get("gap_kind"),
            )
        )
        if (
            goal_continuation_context.get("capability_applied")
            and not goal_continuation_context.get("skipped")
        ):
            events.append(
                event(
                    "goal_continuation_capability_applied",
                    router_winner=goal_continuation_context.get("router_winner"),
                    capability_applied=goal_continuation_context.get("capability_applied"),
                    open_task_id=goal_continuation_context.get("open_task_id"),
                    replan_task_id=goal_continuation_context.get("replan_task_id"),
                    replan_created=goal_continuation_context.get("replan_created"),
                    recovery_hint_applied=goal_continuation_context.get(
                        "recovery_hint_applied"
                    ),
                )
            )
    pipeline = get_pipeline()
    # ``max_tool_rounds`` historically counted LLM rounds, including healthy
    # progress. Keep it as compatibility input, but use a separate Tool-call
    # hard limit and progress-sensitive stop counters for this Agent Loop.
    configured_tool_limit_raw = pipeline.get("agent_tool_absolute_hard_limit")
    configured_tool_limit = (
        int(configured_tool_limit_raw)
        if configured_tool_limit_raw is not None
        else None
    )
    counters = LoopCounters(
        stagnation_limit=int(pipeline.get("agent_stagnation_limit") or 3),
        same_failure_limit=int(pipeline.get("agent_same_failure_limit") or 3),
        no_evidence_limit=int(pipeline.get("agent_no_evidence_limit") or 6),
        configured_tool_limit=configured_tool_limit,
    )
    semantic_warning_enabled = semantic_warning_enabled_from_pipeline(pipeline)
    semantic_bypass_enabled = semantic_warning_enabled
    progress_shadow_tracker = (
        ProgressShadowTracker(semantic_bypass_enabled=semantic_bypass_enabled)
        if orchestrator is not None
        else None
    )
    semantic_warning_tracker = (
        SemanticStagnationWarningTracker(enabled=semantic_warning_enabled)
        if orchestrator is not None
        else None
    )
    _semantic_warning_prior_snapshot = None
    tools = build_production_agent_tools(include_experimental_overlay=False)
    llm_tools = ollama_tools_for_llm(tools)
    trust = chat_trust_path(str(session["session_id"]))
    if orchestrator is not None:
        orchestrator.configure_tool_expectation(
            tools,
            registry_tools=load_registry_tools(),
        )
        mutation_tool = orchestrator.required_mutation_tool()
        if orchestrator.requires_dedicated_sandbox() and orchestrator.runtime.sandbox_session is None:
            # The Runtime, not the LLM, owns both the session identity and root.
            # Establish isolation before a mutation Tool can be called; failure
            # propagates and therefore fails closed before any write attempt.
            sandbox_started = time.perf_counter()
            try:
                sandbox = orchestrator.runtime.start_dedicated_sandbox(
                    DEVELOPMENT_WORKTREE,
                    resolve_configured_sandbox_parent(DEVELOPMENT_WORKTREE),
                )
            except Exception as exc:
                elapsed_ms = max(0, round((time.perf_counter() - sandbox_started) * 1000))
                raise RuntimeError(
                    "Dedicated Sandbox bootstrap failed "
                    f"after {elapsed_ms} ms: {type(exc).__name__}: {exc}"
                ) from exc
            events.append(
                event(
                    "dedicated_sandbox_started",
                    session_id=sandbox.session_id,
                    branch=sandbox.branch,
                    production_applied=sandbox.production_applied,
                    required_tool=mutation_tool,
                )
            )
    grill_return_to_system = False
    skip_agent_loop = False
    if orchestrator is not None and grill_answer is not None:
        applied = orchestrator.apply_human_grill_answer(grill_answer)
        events.append(
            event(
                "conversation_grill_clarification",
                original_request=applied.get("original_request"),
                extracted_path_grounds=applied.get("extracted_path_grounds"),
                goal_status=applied.get("goal_status"),
                selected=applied.get("selected"),
                needs_human_grill=applied.get("needs_human_grill"),
                ground_source=applied.get("ground_source"),
            )
        )
        if orchestrator.needs_human_grill():
            skip_agent_loop = True
            events.append(
                event(
                    "conversation_grill",
                    reason="CONFIRMED_INFO_INSUFFICIENT_FOR_NEXT_TARGET",
                    unique_path_count=(
                        orchestrator.conversation_grill_record()
                        .get("evidence", {})
                        .get("unique_path_count")
                    ),
                    loop="conversation_grill",
                )
            )
        else:
            grill_return_to_system = True
    events.append(
        event(
            "tool_gate",
            trust="chat_session",
            production_trust_unchanged=True,
        )
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{AGENT_CORE_PROMPT}"}
    ]
    if orchestrator is not None:
        messages.append({"role": "system", "content": orchestrator.hint()})
    if goal_continuation_context and goal_continuation_context.get("recovery_hint"):
        counters.recovery_count += 1
        messages.append(
            {
                "role": "system",
                "content": str(goal_continuation_context.get("recovery_hint") or ""),
            }
        )
    history = [
        item
        for item in (session.get("messages") or [])
        if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
    ][-8:]
    for item in history:
        messages.append({"role": item["role"], "content": str(item["content"])})
    messages.append({"role": "user", "content": user_text})
    if not skip_agent_loop:
        events.append(
            event(
                "llm_send",
                model=model,
                material_count=0,
                history_turns=sum(1 for item in history if item.get("role") == "user"),
                dump_all=False,
                note="ResearchRecord 全件は渡していない。会話履歴のみ。",
            )
        )
        events.append(event("llm", model=model, stage="request"))

    executions: list[dict[str, Any]] = []
    answer = ""
    error = None
    cancelled = False
    stop_reason: LoopStopReason | None = None
    runtime_status_report: dict[str, Any] | None = None
    synthesis: dict[str, Any] | None = None
    answer_gate: dict[str, Any] | None = None
    completion_finish_applied = False
    if not skip_agent_loop and llm_tools:
        from ai_tool.tool_calling_capability_bridge import (
            apply_tool_calling_hard_capability_bridge,
        )

        bridge_result = apply_tool_calling_hard_capability_bridge(
            model,
            llm_tools=llm_tools,
            execution_profile=agent_turn_phase_profile("agent_initial_llm"),
        )
        events.append(event("tool_calling_capability_bridge", **bridge_result.as_dict()))
        if bridge_result.capability_gap:
            stop_reason = LoopStopReason.HARD_CAPABILITY_GAP
            runtime_status_report = _runtime_status_report(
                stop_reason,
                counters,
                orchestrator,
            )
        elif bridge_result.routing_performed:
            model = bridge_result.selected_model
            session["model"] = model
    lifecycle = {
        "llm_request_id": None,
        "final_llm_request_started": False,
        "final_llm_request_started_at": None,
        "final_llm_response_received": False,
        "final_llm_response_received_at": None,
        "final_llm_response_length": 0,
        "final_llm_response_empty": True,
        "final_response_accepted": False,
        "final_response_discarded": False,
        "turn_finalization_started_at": None,
        "turn_finalization_finished_at": None,
        "late_response_received": False,
        "turn_closed_before_response": False,
        "empty_reason": None,
    }
    review_iteration = 0
    max_review_iterations = 2
    if skip_agent_loop:
        stop_reason = LoopStopReason.HUMAN_GRILL
        lifecycle["final_llm_response_received"] = True
        lifecycle["final_response_accepted"] = True
        lifecycle["empty_reason"] = None
        lifecycle["final_llm_response_empty"] = False

    def accept_final_response(response: Any, started_at: str, request_id: str) -> bool:
        nonlocal answer, cancelled
        lifecycle["llm_request_id"] = request_id
        lifecycle["final_llm_request_started"] = True
        lifecycle["final_llm_request_started_at"] = started_at
        lifecycle["final_llm_response_received"] = True
        lifecycle["final_llm_response_received_at"] = now_iso()
        content = str(getattr(response.message, "content", None) or "")
        lifecycle["final_llm_response_length"] = len(content)
        lifecycle["final_llm_response_empty"] = not bool(content)
        if not response_is_current(str(session["session_id"]), correlation_id):
            cancelled = True
            lifecycle["final_response_discarded"] = True
            lifecycle["late_response_received"] = True
            lifecycle["empty_reason"] = "RESPONSE_DISCARDED"
            return False
        answer = content
        lifecycle["final_response_accepted"] = True
        lifecycle["empty_reason"] = "MODEL_RETURNED_EMPTY" if not content else None
        return True

    def activity(status: ActivityStatus, *, tool_name: str | None = None) -> None:
        task = orchestrator.task if orchestrator is not None else None
        update_activity(
            str(session["session_id"]),
            correlation_id,
            status,
            tool_name=tool_name,
            current_goal=(orchestrator.runtime.goals[orchestrator.current_goal_id].title if orchestrator else None),
            current_task=task.title if task else None,
            task_status=task.status if task else None,
            progress_state=task.progress_state if task else None,
        )
        events.append(event("activity", status=status.value, tool_name=tool_name))

    response = None
    try:
        while stop_reason is None:
            budget_stop = _pipeline_budget_stop_reason(pipeline_observer)
            if budget_stop is not None:
                stop_reason = budget_stop
                events.append(event("pipeline_budget", status="exceeded"))
                break
            calls = []
            if grill_return_to_system and orchestrator is not None:
                grill_return_to_system = False
                selected_read = orchestrator.pending_selected_read_action()
                if selected_read is not None:
                    calls = [
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=selected_read["tool"],
                                arguments=selected_read["arguments"],
                            )
                        )
                    ]
                    events.append(
                        event(
                            "capability_action_bridge",
                            name=selected_read["tool"],
                            arguments=selected_read["arguments"],
                            selected_by="conversation_grill_goal_reeval",
                        )
                    )
            if not calls and orchestrator is not None:
                definition_action = orchestrator.pending_definition_action()
                if definition_action is not None:
                    calls = [
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=definition_action["tool"],
                                arguments=definition_action["arguments"],
                            )
                        )
                    ]
                    events.append(
                        event(
                            "capability_action_bridge",
                            name=definition_action["tool"],
                            arguments=definition_action["arguments"],
                            selected_by="concept_definition_first",
                        )
                    )
            if not calls and orchestrator is not None:
                continuation = orchestrator.pending_observation_continuation()
                if continuation is not None:
                    calls = [
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=continuation["tool"],
                                arguments=continuation["arguments"],
                            )
                        )
                    ]
                    events.append(
                        event(
                            "capability_action_bridge",
                            name=continuation["tool"],
                            arguments=continuation["arguments"],
                            selected_by="task_observation_continuation",
                        )
                    )
            if not calls:
                activity(ActivityStatus.LLM_WAITING)
                request_started_at = now_iso()
                llm_phase = (
                    "agent_initial_llm" if not executions else "agent_post_tool_llm"
                )
                response = _timed_llm_call(
                    chat_fn,
                    llm_phase,
                    timing,
                    model=model,
                    messages=messages,
                    tools=llm_tools,
                )
                calls = getattr(response.message, "tool_calls", None) or []
                if not response_is_current(str(session["session_id"]), correlation_id):
                    cancelled = True
                    if not calls:
                        accept_final_response(
                            response,
                            request_started_at,
                            f"{correlation_id}-late-final",
                        )
                    else:
                        lifecycle["late_response_received"] = True
                        lifecycle["final_response_discarded"] = True
                        lifecycle["empty_reason"] = "RESPONSE_DISCARDED"
                    activity(ActivityStatus.CANCELLED)
                    break
                messages.append(response.message)
                if not calls and orchestrator is not None:
                    bridge_action = orchestrator.pending_capability_action()
                    if bridge_action is not None:
                        calls = [
                            SimpleNamespace(
                                function=SimpleNamespace(
                                    name=bridge_action["tool"],
                                    arguments=bridge_action["arguments"],
                                )
                            )
                        ]
                        events.append(
                            event(
                                "capability_action_bridge",
                                name=bridge_action["tool"],
                                arguments=bridge_action["arguments"],
                                selected_by="runtime_capability_resolution",
                            )
                        )
            if not calls and orchestrator is not None:
                follow = orchestrator.accept_semantic_followup(
                    str(getattr(getattr(response, "message", None), "content", None) or "")
                )
                if follow.get("action"):
                    calls = [
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=follow["action"]["tool"],
                                arguments=follow["action"]["arguments"],
                            )
                        )
                    ]
                    events.append(
                        event(
                            "capability_action_bridge",
                            name=follow["action"]["tool"],
                            arguments=follow["action"]["arguments"],
                            selected_by="semantic_followup_system_resolve",
                        )
                    )
                elif orchestrator.should_retry_semantic_followup(follow):
                    messages.append(
                        {
                            "role": "system",
                            "content": orchestrator.followup_retry_hint(follow),
                        }
                    )
                    events.append(
                        event(
                            "followup_conversion_retry",
                            reason=follow.get("reason"),
                            need=str(follow.get("need") or "")[:200],
                        )
                    )
                    continue
            if not calls:
                if (
                    local_review_enabled
                    and orchestrator is not None
                    and review_iteration < max_review_iterations
                ):
                    review_iteration += 1
                    review_input = build_review_input(
                        orchestrator, str(getattr(response.message, "content", None) or "")
                    )
                    review_started = time.perf_counter()

                    def timed_review_chat(**kwargs: Any) -> Any:
                        return _timed_llm_call(
                            review_chat_fn or chat_fn,
                            "local_review_llm",
                            timing,
                            **kwargs,
                        )

                    review = call_local_reviewer(
                        timed_review_chat,
                        model=model,
                        review_input=review_input,
                    )
                    validation = validate_review(review, orchestrator)
                    accepted = list(validation["accepted_new_tasks"])
                    record = {
                        "review_iteration": review_iteration,
                        "review_input_summary": {
                            "current_task": review_input["current_task"],
                            "completion_conditions": review_input["completion_conditions"],
                            "evidence_count": len(review_input["relevant_evidence"]),
                            "known_failure_count": len(review_input["known_failures"]),
                        },
                        "structured_review": review.as_dict(),
                        **validation,
                        "final_review_status": validation["review_status"],
                        "elapsed_ms": max(
                            0, round((time.perf_counter() - review_started) * 1000)
                        ),
                    }
                    if accepted:
                        for candidate in accepted:
                            orchestrator.add_review_task(candidate)
                        record["unresolved_conditions_after"] = [
                            condition
                            for task in orchestrator.runtime.tasks.values()
                            if task.status != "complete"
                            for condition in task.completion_conditions
                            if task.condition_status.get(condition) != "SATISFIED"
                        ]
                    orchestrator.record_local_review(record)
                    events.append(
                        event(
                            "local_review",
                            iteration=review_iteration,
                            status=validation["review_status"],
                            accepted_new_task_count=len(accepted),
                            parse_error=review.parse_error,
                        )
                    )
                    if accepted:
                        messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Local review found grounded unresolved work. "
                                    "Continue with the newly registered Current Task.\n"
                                    + orchestrator.hint()
                                ),
                            }
                        )
                        continue
                if orchestrator is not None:
                    bridge = orchestrator.incomplete_goal_bridge_before_break()
                    if bridge is not None:
                        outcome = str(bridge.get("outcome") or "")
                        action = bridge.get("action")
                        if outcome in {"execute", "continuation"} and isinstance(action, dict):
                            calls = [
                                SimpleNamespace(
                                    function=SimpleNamespace(
                                        name=str(action.get("tool") or ""),
                                        arguments=dict(action.get("arguments") or {}),
                                    )
                                )
                            ]
                            events.append(
                                event(
                                    "incomplete_goal_guard",
                                    outcome=outcome,
                                    tool=action.get("tool"),
                                )
                            )
                            continue
                        if outcome == "replan":
                            counters.recovery_count += 1
                            activity(ActivityStatus.RECOVERY_PLANNING)
                            orchestrator.add_local_replan(
                                "Continue incomplete goal work",
                                str(
                                    bridge.get("replan_hint")
                                    or "Use the next safe Runtime action for the Current Task."
                                ),
                            )
                            replan_hint = orchestrator.recovery_hint() or orchestrator.hint()
                            if replan_hint:
                                messages.append({"role": "system", "content": replan_hint})
                            events.append(event("incomplete_goal_guard", outcome=outcome))
                            continue
                        if outcome in {"blocked", "incomplete"}:
                            stop_reason = _INCOMPLETE_GOAL_STOP_REASONS.get(
                                outcome,
                                LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK,
                            )
                            accept_final_response(
                                response,
                                request_started_at,
                                f"{correlation_id}-final-{len(executions) + 1}",
                            )
                            break
                accept_final_response(
                    response,
                    request_started_at,
                    f"{correlation_id}-final-{len(executions) + 1}",
                )
                break
            if calls and orchestrator is not None:
                graph_block = orchestrator.graph_propagation_execution_block()
                if graph_block is not None:
                    events.append(
                        event(
                            "task_change_propagation_execution_blocked",
                            **graph_block,
                        )
                    )
                    stop_reason = LoopStopReason.TASK_CHANGE_PROPAGATION_NON_CONVERGED
                    accept_final_response(
                        response,
                        request_started_at,
                        f"{correlation_id}-final-{len(executions) + 1}",
                    )
                    break
                premise_block = orchestrator.premise_execution_block_for_task()
                if premise_block is not None:
                    events.append(
                        event(
                            "premise_revalidation_execution_blocked",
                            **premise_block,
                        )
                    )
                    stop_reason = LoopStopReason.PREMISE_REVALIDATION_EXECUTION_BLOCKED
                    accept_final_response(
                        response,
                        request_started_at,
                        f"{correlation_id}-final-{len(executions) + 1}",
                    )
                    break
            events.append(event("tool_needed", count=len(calls)))
            for tool_call in calls:
                name = tool_call.function.name
                arguments = tool_call.function.arguments
                normalized_arguments = normalize_arguments(arguments)
                if name == "read_file":
                    normalized_arguments = dict(normalized_arguments)
                    if (
                        normalized_arguments.get("limit") is None
                        and normalized_arguments.get("offset") is None
                    ):
                        path = str(normalized_arguments.get("path") or "").strip()
                        if path:
                            normalized_arguments = runtime_initial_read_arguments(path)
                            arguments = normalized_arguments
                events.append(
                    event(
                        "tool_select",
                        name=name,
                        arguments=normalized_arguments,
                        selected_by="llm",
                    )
                )
                if (
                    orchestrator is not None
                    and orchestrator.path_absent_from_complete_listing(
                        name, normalized_arguments
                    )
                ):
                    result = orchestrator.missing_path_observation(
                        name, normalized_arguments
                    )
                    llm_result = prepare_tool_result_for_llm(name, result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": json.dumps(llm_result, ensure_ascii=False, indent=2),
                        }
                    )
                    continue
                budget_stop = _pipeline_budget_stop_reason(pipeline_observer)
                if budget_stop is not None:
                    stop_reason = budget_stop
                    events.append(event("pipeline_budget", status="exceeded"))
                    break
                events.append(event("tool_call", name=name, status="running"))
                if orchestrator is not None:
                    orchestrator.begin_action(name)
                activity(ActivityStatus.TOOL_RUNNING, tool_name=name)
                tool_started = time.perf_counter()
                observed_via_test_safety_bridge = False
                if name == "run_test_plan" and orchestrator is not None:
                    auth = authorize_tool_execution(
                        name,
                        normalized_arguments,
                        ask_confirm=lambda _n, _a: "y",
                        store_path=trust,
                    )
                    if not auth.get("allowed"):
                        result = blocked_result(
                            name,
                            reason=str(auth.get("decision") or "deny"),
                            arguments=normalized_arguments,
                        )
                    else:
                        result = orchestrator.execute_test_plan_action(
                            normalized_arguments,
                            relevant_tools=orchestrator.relevant_tools(tools),
                        )
                        observed_via_test_safety_bridge = True
                    result["agent_tool_gate"] = auth
                else:
                    result = _execute_agent_tool(
                        name,
                        arguments,
                        trust_path=trust,
                        case_id=case_id,
                        sandbox_session=(
                            orchestrator.runtime.sandbox_session
                            if orchestrator is not None
                            else None
                        ),
                    )
                tool_elapsed_ms = max(
                    0, round((time.perf_counter() - tool_started) * 1000)
                )
                timing["tool_execution_ms"] += tool_elapsed_ms
                timing["tool_executions"].append(
                    {
                        "tool": name,
                        "elapsed_ms": tool_elapsed_ms,
                        "arguments": normalized_arguments,
                    }
                )
                blocked = bool(result.get("blocked_by_agent_tool_gate"))
                normalized_result = normalize_tool_result(result, tool_name=name)
                status = str(normalized_result["status"])
                summary = summarize_tool_result(name, result)
                activity(ActivityStatus.RESULT_AUDITING, tool_name=name)
                audit = None
                evidence_gain = False
                if orchestrator is not None and not observed_via_test_safety_bridge:
                    audit = orchestrator.observe_tool(
                        name,
                        normalized_arguments,
                        normalized_result,
                        summary,
                        relevant_tools=orchestrator.relevant_tools(tools),
                        raw_result=result,
                    )
                    evidence_gain = bool(
                        orchestrator.runtime.actions
                        and orchestrator.runtime.actions[-1].evidence_gain
                    )
                    mutation_evidence_id = orchestrator.record_sandbox_mutation(result)
                    if mutation_evidence_id is not None:
                        evidence_gain = True
                    if evidence_gain:
                        activity(ActivityStatus.EVIDENCE_UPDATING)
                    activity(ActivityStatus.COMPLETION_CHECKING)
                elif orchestrator is not None and observed_via_test_safety_bridge:
                    audit = "ACCEPT"
                    evidence_gain = bool(
                        orchestrator.runtime.actions
                        and orchestrator.runtime.actions[-1].evidence_gain
                    )
                    mutation_evidence_id = orchestrator.record_sandbox_mutation(result)
                    if mutation_evidence_id is not None:
                        evidence_gain = True
                    if evidence_gain:
                        activity(ActivityStatus.EVIDENCE_UPDATING)
                    activity(ActivityStatus.COMPLETION_CHECKING)
                executions.append(
                    {
                        "name": name,
                        "arguments": normalized_arguments,
                        "status": status,
                        "blocked": blocked,
                        "summary": summary,
                        "relevance_audit": audit,
                    }
                )
                if isinstance(summary, dict) and summary.get("composed_section_keys"):
                    events.append(
                        event(
                            "compose",
                            name=name,
                            sections=list(summary.get("composed_section_keys") or []),
                            independent_tool_calls=False,
                            note="Returned sections only. Child TOOL_CALL was not recorded. Tools were not re-executed.",
                        )
                    )
                events.append(
                    event(
                        "tool_result",
                        name=name,
                        status=status,
                        summary=summary,
                    )
                )
                if name == "search_web":
                    events.append(
                        event(
                            "web_search",
                            query=(summary or {}).get("query") if isinstance(summary, dict) else None,
                            hit_count=(summary or {}).get("hit_count") if isinstance(summary, dict) else None,
                            backends_tried=(summary or {}).get("backends_tried") if isinstance(summary, dict) else None,
                            status=status,
                        )
                    )
                if name == "read_url_text":
                    events.append(event("url_fetch", status=status))
                llm_result = prepare_tool_result_for_llm(name, result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        # Preserve the Tool Result Contract for the next LLM round.
                        # Relevance controls Task Evidence, not transport fidelity.
                        "content": json.dumps(llm_result, ensure_ascii=False, indent=2),
                    }
                )
                signature = json.dumps(
                    {"tool": name, "arguments": normalized_arguments, "status": status},
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                )
                counters.observe(signature=signature, status=status, evidence_gain=evidence_gain)
                would_have_stopped_by = counters.stop_reason()
                semantic_warning_applied = (
                    semantic_warning_enabled
                    and would_have_stopped_by is not None
                    and is_semantic_fuse_stop(would_have_stopped_by)
                )
                semantic_bypass_applied = semantic_warning_applied
                stop_reason = resolve_actual_stop_reason(
                    would_have_stopped_by,
                    semantic_warning_enabled=semantic_warning_enabled,
                )
                if (
                    stop_reason is None
                    and max_tool_calls_this_turn is not None
                    and counters.total_tool_calls >= max_tool_calls_this_turn
                ):
                    stop_reason = (
                        _incomplete_goal_stop_reason(orchestrator)
                        if orchestrator is not None
                        else LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK
                    ) or LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK
                    events.append(
                        event(
                            "runtime_task_step_boundary",
                            max_tool_calls=max_tool_calls_this_turn,
                            observed_tool_calls=counters.total_tool_calls,
                        )
                    )
                if semantic_warning_tracker is not None and orchestrator is not None:
                    semantic_warning_tracker.note_active_fuses(
                        active_semantic_warnings(counters)
                    )
                    current_progress_snapshot = snapshot_from_orchestrator(orchestrator)
                    progress_classification = classify_progress_transition(
                        _semantic_warning_prior_snapshot,
                        current_progress_snapshot,
                    )
                    failure_signature = current_progress_snapshot.failure_signature
                    if semantic_warning_applied:
                        warning_payload = semantic_warning_tracker.observe_fuse_trigger(
                            would_have_stopped_by=would_have_stopped_by,
                            tool_sequence=counters.total_tool_calls,
                            counters=counters,
                            classification=progress_classification,
                            action_signature=signature,
                            failure_signature=failure_signature,
                            state_key=state_snapshot_key(current_progress_snapshot),
                        )
                        if warning_payload is not None and warning_payload.get("display"):
                            events.append(
                                event(
                                    "semantic_stagnation_warning",
                                    **warning_payload,
                                )
                            )
                    elif semantic_warning_tracker.warnings:
                        semantic_warning_tracker.observe_post_warning_step(
                            classification=progress_classification,
                            action_signature=signature,
                        )
                    _semantic_warning_prior_snapshot = current_progress_snapshot
                if stop_reason is None and orchestrator is not None and orchestrator.needs_human_grill():
                    stop_reason = LoopStopReason.HUMAN_GRILL
                    events.append(
                        event(
                            "conversation_grill",
                            reason="CONFIRMED_INFO_INSUFFICIENT_FOR_NEXT_TARGET",
                            unique_path_count=(
                                orchestrator.conversation_grill_record()
                                .get("evidence", {})
                                .get("unique_path_count")
                            ),
                        )
                    )
                if (
                    stop_reason is None
                    and orchestrator is not None
                    and orchestrator.needs_goal_completion_human()
                ):
                    stop_reason = LoopStopReason.GOAL_COMPLETION_HUMAN
                    packet = orchestrator.goal_completion_human_record()
                    events.append(
                        event(
                            "goal_completion_human",
                            reason=packet.get("reason"),
                            omitted_paths=packet.get("confirmed_facts"),
                        )
                    )
                if progress_shadow_tracker is not None and orchestrator is not None:
                    if semantic_bypass_applied:
                        progress_shadow_tracker.note_semantic_bypass(
                            would_have_stopped_by=would_have_stopped_by,
                            bypass_applied=True,
                            tool_sequence=counters.total_tool_calls,
                        )
                    shadow_row = progress_shadow_tracker.observe_after_tool(
                        orchestrator=orchestrator,
                        counters=counters,
                        tool_name=name,
                        tool_arguments=normalized_arguments,
                        tool_status=status,
                        would_have_stopped_by=would_have_stopped_by,
                        current_stop_reason=stop_reason,
                        semantic_bypass_applied=semantic_bypass_applied,
                        evidence_gain=evidence_gain,
                        relevance_audit=(
                            str(audit) if audit is not None else None
                        ),
                    )
                    events.append(
                        event(
                            "progress_classification_shadow",
                            **shadow_row,
                        )
                    )
                if stop_reason is not None:
                    break
            if stop_reason is not None:
                break
            events.append(event("llm_input", material_count=len(executions), kind="tool_results"))
            if orchestrator is not None:
                messages.append({"role": "system", "content": orchestrator.hint()})
            recovery = orchestrator.recovery_hint() if orchestrator is not None else None
            if recovery:
                counters.recovery_count += 1
                activity(ActivityStatus.RECOVERY_PLANNING)
                messages.append({"role": "system", "content": recovery})
                if not orchestrator.runtime.replans:
                    activity(ActivityStatus.REPLANNING)
                    orchestrator.add_local_replan(
                        "Try an alternative recovery path",
                        "Use a different safe observation to satisfy the current goal.",
                    )
        if stop_reason is not None:
            runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)
            needs_final_synthesis = not (
                stop_reason in _INCOMPLETE_GOAL_STOP_SET
                and lifecycle["final_llm_response_received"]
                and str(answer or "").strip()
            )
            skip_agent_llm = should_skip_agent_llm_after_stop(stop_reason)
            if skip_agent_llm:
                answer = finalize_exit_answer(
                    stop_reason,
                    existing_answer=answer,
                    runtime_status_report=runtime_status_report,
                    orchestrator=orchestrator,
                )
                lifecycle["final_response_accepted"] = True
                lifecycle["final_llm_response_empty"] = not bool(str(answer or "").strip())
                lifecycle["empty_reason"] = (
                    None if str(answer or "").strip() else "SYSTEM_EXIT_NO_LLM"
                )
            elif (
                not skip_agent_loop
                and needs_final_synthesis
            ):
                # A stop decision still receives one explicit, synchronous final
                # synthesis opportunity. Tools are unavailable in this call.
                activity(ActivityStatus.FINAL_SYNTHESIS)
                started_at = now_iso()
                lifecycle["final_llm_request_started"] = True
                lifecycle["final_llm_request_started_at"] = started_at
                lifecycle["llm_request_id"] = f"{correlation_id}-final-synthesis"
                response = _run_finalization_only(
                    chat_fn=chat_fn,
                    model=model,
                    messages=messages,
                    runtime_status_report=runtime_status_report,
                    timing=timing,
                )
                accept_final_response(
                    response,
                    started_at,
                    str(lifecycle["llm_request_id"]),
                )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        classified = classify_llm_error(error)
        events.append(
            event(
                "error",
                where="ollama",
                kind=classified["kind"],
                message=error,
                user_message=classified["user_message"],
            )
        )
        answer = ""
        if not lifecycle["final_llm_response_received"]:
            lifecycle["empty_reason"] = "RUNTIME_ERROR"
        stop_reason = (
            LoopStopReason.TIMEOUT
            if "timeout" in error.casefold() or "timed out" in error.casefold()
            else LoopStopReason.RUNTIME_ERROR
        )
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)

    if cancelled:
        stop_reason = LoopStopReason.USER_CANCELLED
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)
    elif (
        not error
        and stop_reason is None
        and lifecycle["final_llm_response_received"]
        and not answer.strip()
    ):
        stop_reason = LoopStopReason.LLM_EMPTY_RESPONSE
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)
    elif not error and stop_reason is None:
        if orchestrator is not None and orchestrator.needs_goal_completion_human():
            stop_reason = LoopStopReason.GOAL_COMPLETION_HUMAN
            runtime_status_report = _runtime_status_report(
                stop_reason, counters, orchestrator
            )
        elif orchestrator is not None:
            if (
                lifecycle["final_llm_response_received"]
                and answer.strip()
            ):
                activity(ActivityStatus.FINAL_SYNTHESIS)
                answer, answer_gate = orchestrator.gate_answer(answer)
                synthesis = orchestrator.finish(answer, allow_completion=True)
                completion_finish_applied = True
                root_goal = orchestrator.runtime.goals.get("G1")
                root_goal_complete = (
                    root_goal is not None and root_goal.status == "complete"
                )
                if synthesis.get("ready") and root_goal_complete:
                    stop_reason = LoopStopReason.COMPLETED
                else:
                    stop_reason = (
                        _incomplete_goal_stop_reason(orchestrator)
                        or LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK
                    )
                    runtime_status_report = _runtime_status_report(
                        stop_reason, counters, orchestrator
                    )
            else:
                withheld = _incomplete_goal_stop_reason(orchestrator)
                if withheld is not None:
                    stop_reason = withheld
                    runtime_status_report = _runtime_status_report(
                        stop_reason, counters, orchestrator
                    )
                else:
                    stop_reason = LoopStopReason.GOAL_INCOMPLETE_OPEN_WORK
                    runtime_status_report = _runtime_status_report(
                        stop_reason, counters, orchestrator
                    )
        else:
            # Non-agent chat: no TaskRuntime Goal; not subject to Goal Completion Contract v0.
            stop_reason = LoopStopReason.COMPLETED

    if stop_reason is LoopStopReason.HUMAN_GRILL and runtime_status_report is None:
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)
    if stop_reason is LoopStopReason.GOAL_COMPLETION_HUMAN and runtime_status_report is None:
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)

    if (
        not answer.strip()
        and runtime_status_report is not None
        and stop_reason
        not in {LoopStopReason.HUMAN_GRILL, LoopStopReason.GOAL_COMPLETION_HUMAN}
    ):
        answer = str(runtime_status_report["markdown"])

    if (
        not error
        and not cancelled
        and stop_reason is not None
        and should_system_fast_exit_after_stop(stop_reason)
    ):
        if runtime_status_report is None:
            runtime_status_report = _runtime_status_report(
                stop_reason, counters, orchestrator
            )
        answer = finalize_exit_answer(
            stop_reason,
            existing_answer=answer,
            runtime_status_report=runtime_status_report,
            orchestrator=orchestrator,
        )
        if not executions:
            events.append(event("tool", status="none", name=None))
        events.append(event("final_answer", chars=len(answer or "")))
        events.append(
            event(
                "research_record",
                saved=False,
                note="Chat → ResearchRecord は NOT CONNECTED。Matrix Write は NOT OBSERVED。Search 実行と保存は別。",
            )
        )
        events.append(
            event(
                "system_fast_exit",
                stop_reason=stop_reason.value,
            )
        )
        recorded = _record_mission_memory(
            orchestrator,
            stop_reason,
            determined=True,
            answer=answer,
            correlation_id=correlation_id,
            events=events,
        )
        return _build_system_exit_turn_result(
            stop_reason=stop_reason,
            answer=answer,
            events=events,
            executions=executions,
            orchestrator=orchestrator,
            counters=counters,
            lifecycle=lifecycle,
            runtime_status_report=runtime_status_report,
            memory=memory,
            recorded=recorded,
            semantic_warning_tracker=semantic_warning_tracker,
            progress_shadow_tracker=progress_shadow_tracker,
        )

    if error:
        if runtime_status_report is None and stop_reason is not None:
            runtime_status_report = _runtime_status_report(
                stop_reason, counters, orchestrator
            )
        answer = finalize_exit_answer(
            stop_reason,
            existing_answer=answer,
            runtime_status_report=runtime_status_report,
            orchestrator=orchestrator,
        )
        events.append(
            event(
                "system_fast_exit",
                stop_reason=stop_reason.value if stop_reason is not None else None,
            )
        )
        recorded = _record_mission_memory(
            orchestrator,
            stop_reason,
            determined=False,
            answer=answer,
            correlation_id=correlation_id,
            events=events,
        )
        return _build_system_exit_turn_result(
            stop_reason=stop_reason,
            answer=answer,
            events=events,
            executions=executions,
            orchestrator=orchestrator,
            counters=counters,
            lifecycle=lifecycle,
            runtime_status_report=runtime_status_report,
            memory=memory,
            recorded=recorded,
            semantic_warning_tracker=semantic_warning_tracker,
            progress_shadow_tracker=progress_shadow_tracker,
            error=error,
            classified=classified,
        )

    if cancelled:
        if runtime_status_report is None and stop_reason is not None:
            runtime_status_report = _runtime_status_report(
                stop_reason, counters, orchestrator
            )
        answer = finalize_exit_answer(
            stop_reason,
            existing_answer=answer,
            runtime_status_report=runtime_status_report,
            orchestrator=orchestrator,
        )
        events.append(
            event(
                "system_fast_exit",
                stop_reason=stop_reason.value if stop_reason is not None else None,
            )
        )
        recorded = _record_mission_memory(
            orchestrator,
            stop_reason,
            determined=False,
            answer=answer,
            correlation_id=correlation_id,
            events=events,
        )
        return _build_system_exit_turn_result(
            stop_reason=stop_reason,
            answer=answer,
            events=events,
            executions=executions,
            orchestrator=orchestrator,
            counters=counters,
            lifecycle=lifecycle,
            runtime_status_report=runtime_status_report,
            memory=memory,
            recorded=recorded,
            semantic_warning_tracker=semantic_warning_tracker,
            progress_shadow_tracker=progress_shadow_tracker,
            cancelled=True,
        )

    if not executions:
        events.append(event("tool", status="none", name=None))
    web_used = any(e["name"] in {"search_web", "read_url_text"} for e in executions)
    confirmed_gaps = (
        [
            item
            for item in orchestrator.runtime.tool_gaps.values()
            if item.status == "confirmed" and item.requires_human_approval
        ]
        if orchestrator is not None
        else []
    )
    if confirmed_gaps:
        stop_reason = LoopStopReason.APPROVAL_REQUIRED
        runtime_status_report = _runtime_status_report(stop_reason, counters, orchestrator)
        proposals = "\n".join(
            f"- {item.required_capability}: {item.suggested_minimal_tool or '最小Toolを要検討'}"
            for item in confirmed_gaps
        )
        answer = (
            (answer.rstrip() + "\n\n" if answer.strip() else "")
            + "不足Capabilityを確認しました。Toolは自動作成しません。\n"
            + proposals
            + "\n追加する場合はHuman Approvalが必要です。"
        )
        events.append(event("human_approval_required", reason="confirmed_tool_gap"))
    if orchestrator is not None and not completion_finish_applied:
        activity(ActivityStatus.FINAL_SYNTHESIS)
        answer, answer_gate = orchestrator.gate_answer(answer)
        synthesis = orchestrator.finish(
            answer,
            allow_completion=stop_reason
            in {
                LoopStopReason.COMPLETED,
                LoopStopReason.GOAL_COMPLETION_HUMAN,
            },
        )
    if (
        runtime_status_report is None
        and stop_reason == LoopStopReason.COMPLETED
        and orchestrator is not None
        and answer_gate
        and not answer_gate.get("verified")
    ):
        runtime_status_report = _runtime_status_report(
            stop_reason, counters, orchestrator
        )
        next_actions = list(runtime_status_report.get("next_actions") or [])
        if next_actions and "次に可能な対応" not in answer:
            answer = answer.rstrip() + "\n\n" + "次に可能な対応:\n" + "\n".join(
                f"- {item}" for item in next_actions
            )
        events.append(
            event(
                "execution_end_status",
                reason_code=runtime_status_report.get("reason_code"),
                next_actions=next_actions,
                answer_gate_reason=answer_gate.get("reason"),
            )
        )
    events.append(event("final_answer", chars=len(answer or "")))
    events.append(
        event(
            "research_record",
            saved=False,
            note="Chat → ResearchRecord は NOT CONNECTED。Matrix Write は NOT OBSERVED。Search 実行と保存は別。",
        )
    )
    recorded = _record_mission_memory(
        orchestrator,
        stop_reason,
        determined=True,
        answer=answer,
        correlation_id=correlation_id,
        events=events,
    )
    awaiting_human_review = bool(confirmed_gaps)
    awaiting_human_grill = bool(
        orchestrator is not None and orchestrator.needs_human_grill()
    )
    awaiting_goal_completion_human = bool(
        orchestrator is not None and orchestrator.needs_goal_completion_human()
    )
    human_priority_blocked = (
        awaiting_human_review
        or awaiting_human_grill
        or awaiting_goal_completion_human
        or stop_reason
        in {
            LoopStopReason.GOAL_COMPLETION_HUMAN,
            LoopStopReason.HUMAN_GRILL,
            LoopStopReason.APPROVAL_REQUIRED,
        }
    )
    continuation_progress = None
    continuation_progress_blocked = False
    continuation_help_escalation = False
    continuation_stagnation_count = 0
    current_gap_snapshot = None
    pre_decision = None
    regression_reroute = None
    regression_superseded_winner = None
    if orchestrator is not None:
        from ai_tool.chat_interface.gap_resolution_router import (
            route_gap_resolution_from_orchestrator,
        )

        pre_decision = route_gap_resolution_from_orchestrator(
            orchestrator,
            stop_reason=stop_reason.value if stop_reason is not None else None,
            answer_gate=answer_gate,
            loop_counters=counters.snapshot(),
        )
        current_gap_snapshot = capture_gap_snapshot(
            orchestrator,
            gap_kind=pre_decision.gap_kind,
            gap_resolved=pre_decision.gap_resolved,
            answer_gate=answer_gate,
        ).as_dict()
        if goal_continuation_context:
            continuation_stagnation_count = int(
                goal_continuation_context.get("continuation_stagnation_count") or 0
            )
            continuation_progress = observe_goal_continuation_progress(
                orchestrator,
                prior_snapshot=goal_continuation_context.get("gap_snapshot"),
                gap_kind=pre_decision.gap_kind,
                gap_resolved=pre_decision.gap_resolved,
                answer_gate=answer_gate,
                continuation_stagnation_count=continuation_stagnation_count,
            )
            if continuation_progress is not None:
                continuation_stagnation_count = (
                    continuation_progress.continuation_stagnation_count
                )
                continuation_progress_blocked = continuation_progress.continuation_blocked
                continuation_help_escalation = continuation_progress.help_escalation
                events.append(
                    event("goal_continuation_progress", **continuation_progress.as_dict())
                )
                if (
                    continuation_progress.regression_detected
                    and pre_decision is not None
                ):
                    pre_decision, regression_reroute_bridge = (
                        apply_regression_continuation_bridge(
                            pre_decision,
                            prior_winner=str(
                                goal_continuation_context.get("winner") or ""
                            )
                            or None,
                            human_priority_blocked=human_priority_blocked,
                        )
                    )
                    if regression_reroute_bridge is not None:
                        regression_reroute = regression_reroute_bridge.as_dict()
                        regression_superseded_winner = (
                            regression_reroute_bridge.superseded_winner
                        )
                        continuation_help_escalation = (
                            continuation_help_escalation
                            or regression_reroute_bridge.help_escalation
                        )
                        if regression_reroute_bridge.block_continuation_resume:
                            continuation_progress_blocked = True
                        elif regression_reroute_bridge.reroute_winner:
                            continuation_progress_blocked = False
                        events.append(
                            event(
                                "goal_continuation_regression_reroute",
                                **regression_reroute,
                            )
                        )
    gap_resolution_decision, goal_continuation_resume, gap_resolution_event = (
        observe_gap_resolution_at_execution_end(
            orchestrator,
            stop_reason=stop_reason.value if stop_reason is not None else None,
            answer_gate=answer_gate,
            loop_counters=counters.snapshot(),
            correlation_id=correlation_id,
            recorded=recorded,
            human_priority_blocked=human_priority_blocked,
            gap_snapshot=current_gap_snapshot,
            continuation_stagnation_count=continuation_stagnation_count,
            block_continuation_resume=continuation_progress_blocked,
            help_escalation=continuation_help_escalation,
            decision=pre_decision,
            regression_reroute=regression_reroute,
            superseded_winner=regression_superseded_winner,
        )
    )
    if gap_resolution_event is not None:
        events.append(event("gap_resolution_routed", **gap_resolution_event))
    awaiting_boundary_grill = False
    boundary_grill = None
    boundary_grill_state = None
    if (
        orchestrator is not None
        and gap_resolution_decision is not None
        and should_launch_boundary_grill(
            gap_resolution_decision,
            human_priority_blocked=human_priority_blocked,
        )
    ):
        launched = launch_boundary_grill(orchestrator, gap_resolution_decision)
        answer = launched["formatted"]
        boundary_grill = launched["record"]
        boundary_grill_state = launched["state"]
        awaiting_boundary_grill = True
        goal_continuation_resume = None
        events.append(event("boundary_grill", **boundary_grill))
        events.append(
            event(
                "boundary_grill_launched",
                contract=launched["contract"],
                winner=gap_resolution_decision.winner,
            )
        )
    if (
        continuation_help_escalation
        and orchestrator is not None
        and regression_reroute is not None
        and regression_reroute.get("reroute_reason") == "regression_replan_unavailable"
    ):
        runtime_status_report = _runtime_status_report(
            LoopStopReason.GOAL_CONTINUATION_REGRESSION,
            counters,
            orchestrator,
        )
        regression_reasons = (
            list(continuation_progress.reasons or [])
            if continuation_progress is not None
            else []
        )
        if regression_reasons:
            runtime_status_report = {
                **runtime_status_report,
                "markdown": (
                    runtime_status_report["markdown"]
                    + "\n回帰理由: "
                    + ", ".join(regression_reasons)
                ),
            }
        next_actions = list(runtime_status_report.get("next_actions") or [])
        if next_actions and "次に可能な対応" not in answer:
            answer = answer.rstrip() + "\n\n" + "次に可能な対応:\n" + "\n".join(
                f"- {item}" for item in next_actions
            )
        events.append(
            event(
                "execution_end_status",
                reason_code=runtime_status_report.get("reason_code"),
                next_actions=next_actions,
                continuation_regression=True,
            )
        )
    result = {
        "route": "chat",
        "answer": answer,
        "events": events,
        "tool_used": bool(executions),
        "tools": executions,
        "web_search": web_used,
        "research_saved": False,
        "error": error,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": orchestrator.snapshot() if orchestrator else None,
        "final_synthesis": synthesis,
        "final_llm_lifecycle": lifecycle,
        "runtime_status_report": runtime_status_report,
        "loop_counters": counters.snapshot(),
        "answer_gate": answer_gate,
        "gap_resolution": (
            gap_resolution_decision.as_dict() if gap_resolution_decision is not None else None
        ),
        "goal_continuation_resume": goal_continuation_resume,
        "awaiting_goal_continuation": (
            goal_continuation_resume is not None and not awaiting_boundary_grill
        ),
        "goal_continuation_help_escalation": continuation_help_escalation,
        "awaiting_boundary_grill": awaiting_boundary_grill,
        "boundary_grill": boundary_grill,
        "boundary_grill_state": boundary_grill_state,
        "awaiting_human_review": awaiting_human_review,
        "awaiting_human_grill": awaiting_human_grill,
        "awaiting_goal_completion_human": awaiting_goal_completion_human,
        "conversation_grill": (
            orchestrator.conversation_grill_record()
            if orchestrator is not None and orchestrator.needs_human_grill()
            else None
        ),
        "goal_completion_human": (
            orchestrator.goal_completion_human_record()
            if orchestrator is not None and orchestrator.needs_goal_completion_human()
            else None
        ),
        "goal_completion_resume": None,
        "tool_gap_proposals": [asdict(item) for item in confirmed_gaps],
        "mission_memory": recorded,
        "progress_classification_shadow": (
            progress_shadow_tracker.finalize_and_as_dict(
                actual_stop_reason=stop_reason,
                orchestrator=orchestrator,
            )
            if progress_shadow_tracker is not None
            else None
        ),
        "semantic_stagnation_warning": (
            _finalize_semantic_warning_tracker(
                semantic_warning_tracker,
                actual_stop_reason=stop_reason,
                orchestrator=orchestrator,
            )
            if semantic_warning_tracker is not None
            else None
        ),
    }
    if result["awaiting_goal_completion_human"] and orchestrator is not None:
        resume = orchestrator.goal_completion_resume_state()
        if recorded:
            resume["evidence_refs"] = list(recorded.get("evidence_refs") or [])
            resume["prior_execution_id"] = recorded.get("execution_id")
        result["goal_completion_resume"] = resume
    if goal_continuation_context:
        result["goal_continuation_restored"] = True
        result["goal_continuation_prior_execution_id"] = goal_continuation_context.get(
            "prior_execution_id"
        )
    return result



def _goal_continuation_restore_failed_turn(
    *,
    correlation_id: str,
    memory: dict[str, Any],
    reason: str,
    errors: list[str],
) -> dict[str, Any]:
    """Return a blocked turn when continuation restore is unsafe. No new Mission."""
    message = (
        "Goal continuation の復元に失敗しました。新しい Mission は開始していません。\n\n"
        f"理由: {reason}\n"
        f"詳細: {', '.join(errors) if errors else 'NOT_OBSERVED'}"
    )
    return {
        "route": "chat",
        "answer": message,
        "events": [
            event(
                "goal_continuation_restore_failed",
                reason=reason,
                errors=errors,
            )
        ],
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": None,
        "goal_continuation_restore_failed": True,
        "goal_continuation_restore_errors": errors,
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-goal-continuation-restore-failed",
            "final_llm_request_started": False,
            "final_llm_response_received": False,
            "empty_reason": "GOAL_CONTINUATION_RESTORE_FAILED",
        },
        "runtime_status_report": {
            "status": "BLOCKED",
            "reason_code": "GOAL_CONTINUATION_RESTORE_FAILED",
            "next_actions": ["継続パケットを確認してから、再度「継続」を送信してください"],
            "markdown": message,
        },
    }


def _apply_prepared_boundary_grill_answer(
    orchestrator: Any,
    user_text: str,
    contract: dict[str, Any],
    prepared: dict[str, Any],
) -> dict[str, Any]:
    conflict_class = str(prepared.get("conflict_class") or "")
    if conflict_class == "duplicate":
        prior = dict(prepared.get("prior") or {})
        return {
            "applied": True,
            "duplicate": True,
            "dimension": prior.get("dimension"),
            "decision_id": prior.get("decision_id"),
            "decision_key": prior.get("decision_key"),
            "selected_label": prior.get("text"),
            "open_dimensions": [],
            "needs_more_boundary_grill": False,
        }
    supersede_prior_id = None
    if conflict_class == "concretization" and prepared.get("prior_decision_id"):
        supersede_prior_id = str(prepared.get("prior_decision_id") or "")
    return apply_boundary_grill_answer(
        orchestrator,
        user_text,
        contract,
        proposed=dict(prepared.get("proposed") or {}),
        supersede_prior_id=supersede_prior_id,
    )


def _decision_supersede_triggered(
    events: list[dict[str, Any]],
    applied: Mapping[str, Any],
) -> bool:
    if applied.get("superseded_prior_id"):
        return True
    return any(str(item.get("type") or "") == "decision_superseded" for item in events)


def _run_post_supersede_premise_revalidations(
    orchestrator: Any,
    events: list[dict[str, Any]],
    *,
    chat_fn: ChatFn | None,
    model: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Run semantic premise revalidation for affected tasks after Decision supersede."""
    from ai_tool.decision_premise_revalidation import run_premise_revalidations

    if chat_fn is None:
        events.append(
            event(
                "premise_revalidation_skipped",
                reason="chat_fn_not_configured",
            )
        )
        return [], None
    results = run_premise_revalidations(orchestrator, chat_fn=chat_fn, model=model)
    propagation_result: dict[str, Any] | None = None
    if not results:
        events.append(event("premise_revalidation_applied", task_count=0))
    else:
        for row in results:
            events.append(
                event(
                    "premise_revalidation_applied",
                    task_id=row.get("task_id"),
                    outcome=row.get("outcome"),
                    reason=row.get("reason"),
                )
            )
    from ai_tool.premise_corrective_replan import run_premise_corrective_replans

    corrective_rows = run_premise_corrective_replans(orchestrator, results)
    for row in corrective_rows:
        events.append(
            event(
                "premise_corrective_replan_applied",
                source_task_id=row.get("source_task_id"),
                corrective_task_id=row.get("corrective_task_id"),
                outcome=row.get("outcome"),
                reason=row.get("reason"),
            )
        )
    from ai_tool.premise_pending_replacement import run_premise_pending_replacements

    replacement_rows = run_premise_pending_replacements(orchestrator, results)
    for row in replacement_rows:
        events.append(
            event(
                "premise_pending_replacement_applied",
                source_task_id=row.get("source_task_id"),
                replacement_task_id=row.get("replacement_task_id"),
                outcome=row.get("outcome"),
                reason=row.get("reason"),
                redirected_dependents=row.get("redirected_dependents"),
            )
        )
    successor_rows = [*corrective_rows, *replacement_rows]
    if successor_rows:
        from ai_tool.task_upstream_supersession_revalidation import (
            new_propagation_id,
            resolve_changes_for_propagation,
            run_task_change_propagation,
        )

        initial_changes = resolve_changes_for_propagation(orchestrator, successor_rows)
        propagation_result = run_task_change_propagation(
            orchestrator,
            initial_changes,
            chat_fn=chat_fn,
            model=model,
            propagation_id=new_propagation_id(),
        )
        from ai_tool.task_change_propagation_guard import get_propagation_guard

        events.append(
            event(
                "task_change_propagation_completed",
                propagation_id=propagation_result.get("propagation_id"),
                completed_wave_count=propagation_result.get("completed_wave_count"),
                processed_change_sets=propagation_result.get("processed_change_sets"),
                successor_history=propagation_result.get("successor_history"),
                held_tasks=propagation_result.get("held_tasks"),
                stop_reason=propagation_result.get("stop_reason"),
                converged=propagation_result.get("converged"),
                task_change_propagation_guard=get_propagation_guard(orchestrator),
            )
        )
        for wave_result in propagation_result.get("waves") or []:
            events.append(
                event(
                    "upstream_supersession_wave_completed",
                    propagation_id=wave_result.get("propagation_id"),
                    completed_wave_index=wave_result.get("completed_wave_index"),
                    successor_changes=wave_result.get("successor_changes"),
                )
            )
            for row in wave_result.get("evaluations") or []:
                events.append(
                    event(
                        "upstream_supersession_revalidation_applied",
                        downstream_task_id=row.get("downstream_task_id"),
                        propagation_id=row.get("propagation_id"),
                        wave_index=row.get("wave_index"),
                        upstream_changes=row.get("upstream_changes"),
                        change_set_identity=row.get("change_set_identity"),
                        outcome=row.get("outcome"),
                        reason=row.get("reason"),
                        skipped=row.get("skipped"),
                    )
                )
            for row in wave_result.get("consumed") or []:
                events.append(
                    event(
                        "upstream_supersession_outcome_consumed",
                        downstream_task_id=row.get("downstream_task_id"),
                        old_task_id=row.get("old_task_id"),
                        new_task_id=row.get("new_task_id"),
                        outcome=row.get("outcome"),
                        task_status=row.get("task_status"),
                        successor_source=row.get("successor_source"),
                        skipped=row.get("skipped"),
                    )
                )
    return results, propagation_result


def _boundary_grill_post_apply_reroute(
    orchestrator: Any,
    *,
    events: list[dict[str, Any]],
    correlation_id: str,
    memory: dict[str, Any],
    model: str,
    applied: dict[str, Any],
    stop_reason: str,
    lifecycle_suffix: str,
    session: dict[str, Any] | None = None,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    propagation_note: str | None = None
    effective_stop_reason = stop_reason
    if _decision_supersede_triggered(events, applied):
        _results, propagation_result = _run_post_supersede_premise_revalidations(
            orchestrator,
            events,
            chat_fn=chat_fn,
            model=model,
        )
        from ai_tool.task_change_propagation_guard import (
            effective_stop_reason_for_boundary_grill,
        )

        effective_stop_reason, propagation_note = effective_stop_reason_for_boundary_grill(
            stop_reason,
            orchestrator,
        )
    answer, answer_gate = orchestrator.gate_answer("")
    if propagation_note:
        answer = (
            f"{answer}\n\n{propagation_note}".strip()
            if str(answer or "").strip()
            else propagation_note
        )
    synthesis = orchestrator.finish(answer, allow_completion=False)
    decision, reroute_payload = reroute_after_boundary_grill_answer(
        orchestrator,
        stop_reason=effective_stop_reason,
        answer_gate=answer_gate,
    )
    events.append(event("boundary_grill_reroute", **reroute_payload))
    events.append(
        event(
            "gap_resolution_routed",
            gap_kind=decision.gap_kind,
            gap_resolved=decision.gap_resolved,
            winner=decision.winner,
            continuation_resume_persisted=False,
            human_priority_blocked=False,
            boundary_grill_reroute=True,
        )
    )
    awaiting_boundary_grill = False
    boundary_grill = None
    boundary_grill_state = None
    goal_continuation_resume = None
    awaiting_goal_continuation = False
    runtime_status_report = None
    needs_more_boundary = bool(applied.get("needs_more_boundary_grill")) or bool(
        boundary_grill_open_dimensions(orchestrator)
    )
    if should_launch_boundary_grill(decision, human_priority_blocked=False) or (
        needs_more_boundary and boundary_grill_runtime_connected()
    ):
        launched = launch_boundary_grill(orchestrator, decision)
        answer = launched["formatted"]
        boundary_grill = launched["record"]
        boundary_grill_state = launched["state"]
        awaiting_boundary_grill = True
        events.append(event("boundary_grill", **boundary_grill))
        events.append(
            event(
                "boundary_grill_launched",
                mission_id=orchestrator.mission_id,
                execution_id=orchestrator.execution_id,
                open_dimensions=boundary_grill_open_dimensions(orchestrator),
            )
        )
    elif session is not None and not session_has_production_handoff(session):
        readiness = assess_production_handoff_readiness(
            orchestrator,
            session=session,
            gap_decision=decision,
            awaiting_boundary_grill=False,
            awaiting_decision_change_confirmation=False,
            trigger="auto",
        )
        events.append(
            event(
                "production_handoff_readiness",
                **readiness.as_dict(),
                trigger="auto",
            )
        )
        if readiness.ready and not orchestrator_has_goal_handoff_seed(orchestrator):
            plan_tasks = session.get("production_handoff_plan_tasks")
            pipeline = run_production_handoff_pipeline(
                orchestrator,
                initial_request=str(getattr(orchestrator, "request", "") or ""),
                chat_fn=chat_fn,
                model=model,
                plan_tasks=plan_tasks if isinstance(plan_tasks, list) else None,
                handoff_slug=f"session-{session.get('session_id') or correlation_id}",
            )
            return _build_production_handoff_turn_result(
                orchestrator,
                pipeline,
                session=session,
                correlation_id=correlation_id,
                model=model,
                memory=memory,
                events=events,
                trigger="auto",
                lifecycle_suffix="production-handoff-auto",
            )
    elif not awaiting_boundary_grill and decision.winner == CapabilityId.HELP.value:
        runtime_status_report = _runtime_status_report(
            LoopStopReason.GOAL_CONTINUATION_REGRESSION,
            LoopCounters(
                stagnation_limit=0,
                same_failure_limit=0,
                no_evidence_limit=0,
            ),
            orchestrator,
        )
        answer = (
            "Boundary Grill の判断を保存しましたが、次の自動経路はありません。\n\n"
            + str(runtime_status_report.get("markdown") or "")
        )
    elif should_persist_goal_continuation_resume(
        decision,
        human_priority_blocked=False,
    ):
        goal_continuation_resume = build_goal_continuation_resume(
            orchestrator,
            decision,
            recorded={
                "mission_id": orchestrator.mission_id,
                "execution_id": orchestrator.execution_id,
            },
            correlation_id=correlation_id,
        )
        awaiting_goal_continuation = goal_continuation_resume is not None
        answer = (
            "Boundary Grill の判断を反映しました。"
            f" 次の継続 winner: {decision.winner}"
        )
    elif applied.get("duplicate"):
        answer = "Boundary Grill の判断は既に確定済みです。Router を再評価しました。"
    else:
        answer = (
            "Boundary Grill の判断を反映しました。"
            f" gap_resolved={decision.gap_resolved}, winner={decision.winner}"
        )
    if propagation_note and propagation_note not in str(answer or ""):
        answer = (
            f"{answer}\n\n{propagation_note}".strip()
            if str(answer or "").strip()
            else propagation_note
        )
    recorded = persist_chat_execution(
        orchestrator,
        stop_reason=effective_stop_reason,
        determined=True,
        answer=answer,
        correlation_id=correlation_id,
    )
    events.append(
        event(
            "mission_memory",
            status="saved",
            mission_id=recorded.get("mission_id"),
            execution_id=recorded.get("execution_id"),
        )
    )
    timestamp = now_iso()
    return {
        "route": "chat",
        "answer": answer,
        "events": events,
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": orchestrator.snapshot(),
        "final_synthesis": synthesis,
        "answer_gate": answer_gate,
        "gap_resolution": decision.as_dict(),
        "awaiting_boundary_grill": awaiting_boundary_grill,
        "boundary_grill": boundary_grill,
        "boundary_grill_state": boundary_grill_state,
        "goal_continuation_resume": goal_continuation_resume,
        "awaiting_goal_continuation": awaiting_goal_continuation,
        "awaiting_decision_change_confirmation": False,
        "decision_change_confirmation_state": None,
        "mission_memory": recorded,
        "runtime_status_report": runtime_status_report,
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-{lifecycle_suffix}",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": not bool(answer.strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
    }


def _sync_session_mission_pointer(
    session: dict[str, Any],
    result: Mapping[str, Any],
) -> None:
    recorded = result.get("mission_memory") or {}
    if isinstance(recorded, Mapping) and recorded.get("mission_id"):
        session["last_mission_id"] = str(recorded["mission_id"])
    runtime = result.get("task_runtime") or {}
    if isinstance(runtime, Mapping):
        original = str(runtime.get("original_request") or "").strip()
        if original:
            session["last_original_request"] = original
    if not str(session.get("last_original_request") or "").strip():
        for key in (
            "boundary_grill_state",
            "goal_completion_resume",
            "goal_continuation_resume",
            "conversation_grill_state",
        ):
            packet = result.get(key) or {}
            if isinstance(packet, Mapping):
                original = str(packet.get("original_request") or "").strip()
                if original:
                    session["last_original_request"] = original
                    break


def _build_production_handoff_turn_result(
    orchestrator: ChatTaskOrchestrator,
    pipeline: Mapping[str, Any],
    *,
    session: dict[str, Any],
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    events: list[dict[str, Any]],
    trigger: str,
    lifecycle_suffix: str,
) -> dict[str, Any]:
    packet = dict(pipeline.get("handoff_packet") or {})
    handoff_id = str(packet.get("handoff_id") or "")
    mark_session_production_handoff_completed(session, handoff_id=handoff_id)
    if trigger == "auto":
        answer = (
            "仕様形成が完了したため Goal Handoff を生成し、"
            "implementation_tasks を Runtime に seed しました。\n"
            f"handoff_id={handoff_id}"
        )
    else:
        answer = (
            "Goal Handoff を生成し、implementation_tasks を Runtime に seed しました。\n"
            f"handoff_id={handoff_id}"
        )
    events.append(
        event(
            "production_handoff_pipeline_completed",
            handoff_id=handoff_id,
            task_count=len(packet.get("implementation_tasks") or []),
            decision_keys=sorted((pipeline.get("decision_catalog") or {}).keys()),
            trigger=trigger,
        )
    )
    if trigger == "auto":
        events.append(event("production_handoff_auto_triggered", handoff_id=handoff_id))
    try:
        recorded = persist_chat_execution(
            orchestrator,
            stop_reason="PRODUCTION_HANDOFF",
            determined=True,
            answer=answer,
            correlation_id=correlation_id,
        )
        events.append(
            event(
                "mission_memory",
                status="saved",
                mission_id=recorded.get("mission_id"),
                execution_id=recorded.get("execution_id"),
            )
        )
    except MissionMemoryError as exc:
        recorded = {"ok": False, "error": str(exc)}
        events.append(event("mission_memory", status="error", error=str(exc)))
    timestamp = now_iso()
    return {
        "route": "chat",
        "answer": answer,
        "events": events,
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": orchestrator.snapshot(),
        "handoff_packet": packet,
        "production_handoff": {
            "handoff_id": handoff_id,
            "decision_catalog": pipeline.get("decision_catalog"),
            "trigger": trigger,
        },
        "production_handoff_auto_triggered": trigger == "auto",
        "awaiting_boundary_grill": False,
        "boundary_grill": None,
        "boundary_grill_state": None,
        "awaiting_decision_change_confirmation": False,
        "decision_change_confirmation_state": None,
        "mission_memory": recorded,
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-{lifecycle_suffix}",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": False,
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
    }


def _production_handoff_turn(
    user_text: str,
    session: dict[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    chat_fn: ChatFn | None,
) -> dict[str, Any]:
    mission_id = str(session.get("last_mission_id") or "").strip()
    if not mission_id:
        answer = (
            "Goal Handoff を生成できません。"
            "先に Human Decision を確定した Production Chat 実行が必要です。"
        )
        return {
            "route": "chat",
            "answer": answer,
            "events": [event("production_handoff_blocked", reason="missing_mission_id")],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "production_handoff_error": "missing_mission_id",
        }
    if session_has_production_handoff(session):
        answer = (
            "Goal Handoff は既に発行済みです。"
            f" handoff_id={session.get('production_handoff_id')}"
        )
        return {
            "route": "chat",
            "answer": answer,
            "events": [
                event(
                    "production_handoff_blocked",
                    reason="handoff_already_issued",
                    handoff_id=session.get("production_handoff_id"),
                )
            ],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "production_handoff_error": "handoff_already_issued",
        }
    original_request = str(session.get("last_original_request") or user_text).strip()
    orchestrator = ChatTaskOrchestrator(correlation_id, original_request)
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id,
        new_execution=True,
    )
    prepare_production_handoff_orchestrator(orchestrator)
    readiness = assess_production_handoff_readiness(
        orchestrator,
        session=session,
        trigger="explicit",
        awaiting_boundary_grill=bool(session.get("awaiting_boundary_grill")),
        awaiting_decision_change_confirmation=bool(
            session.get("awaiting_decision_change_confirmation")
        ),
    )
    events = [event("production_handoff_readiness", **readiness.as_dict(), trigger="explicit")]
    if not readiness.ready:
        answer = (
            "Goal Handoff を生成できません。"
            f" blockers={', '.join(readiness.blockers)}"
        )
        return {
            "route": "chat",
            "answer": answer,
            "events": events,
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": orchestrator.snapshot(),
            "production_handoff_error": readiness.blockers[0] if readiness.blockers else "not_ready",
        }
    plan_tasks = session.get("production_handoff_plan_tasks")
    pipeline = run_production_handoff_pipeline(
        orchestrator,
        initial_request=original_request,
        chat_fn=chat_fn,
        model=model,
        plan_tasks=plan_tasks if isinstance(plan_tasks, list) else None,
        handoff_slug=f"session-{session.get('session_id') or correlation_id}",
    )
    return _build_production_handoff_turn_result(
        orchestrator,
        pipeline,
        session=session,
        correlation_id=correlation_id,
        model=model,
        memory=memory,
        events=events,
        trigger="explicit",
        lifecycle_suffix="production-handoff",
    )


def _requirement_resolution_heuristic_enabled() -> bool:
    return os.environ.get("AI_TOOL_REQUIREMENT_RESOLUTION_HEURISTIC", "").lower() in (
        "1",
        "true",
        "yes",
    )


def _blocks_new_goal_seed(
    *,
    requirement_resolution_packet: dict[str, Any] | None,
    production_grill_packet: dict[str, Any] | None,
    goal_continuation_packet: dict[str, Any] | None,
    goal_continuation_restore_errors: list[str] | None,
    production_handoff_requested: bool,
) -> bool:
    """Pending reply / continuation execution must not start a new Goal."""
    return bool(
        requirement_resolution_packet is not None
        or production_grill_packet is not None
        or goal_continuation_packet is not None
        or goal_continuation_restore_errors
        or production_handoff_requested
    )


def _should_start_production_grill_on_new_goal(
    *,
    handoff_packet: Mapping[str, Any] | None,
    text: str,
    explicit_goal_command: bool = False,
) -> bool:
    """Phase1 belongs to formally adopted production/implementation Goals only."""
    if handoff_packet is not None:
        return True
    return explicit_goal_command or has_creation_intent(text)


def _canonical_handoff_hash(packet: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(packet), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _phase3a_command_result(
    *,
    session: dict[str, Any],
    correlation_id: str,
    memory: dict[str, Any],
    model: str,
    chat_fn: ChatFn,
    goal_usage: bool,
    run_requested: bool,
) -> dict[str, Any] | None:
    if goal_usage:
        return {
            "route": "chat",
            "answer": "/goal <達成したい内容>",
            "events": [event("production_goal_usage")],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "runtime_started": False,
        }
    if not run_requested:
        return None

    saved = session.get("production_handoff_packet")
    packet = json.loads(json.dumps(saved, ensure_ascii=False)) if isinstance(saved, Mapping) else None
    errors = validate_handoff_packet(packet or {})
    mission_id = str(session.get("last_mission_id") or "").strip()
    mission = MissionMemoryStore.from_default().get_mission(mission_id) if mission_id else None
    if packet is not None:
        errors.extend(validate_handoff_source_binding(packet, mission))
        errors = sorted(set(errors))
    if packet is None or str(packet.get("status") or "") != "ready" or errors:
        return {
            "route": "chat",
            "answer": "実行可能な確定済みGoalがありません。先に `/goal ...` でGoalを確定してください。",
            "events": [event("production_run_blocked", reason="missing_or_invalid_handoff")],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "runtime_prepared": False,
            "runtime_started": False,
            "production_run_error": "missing_or_invalid_handoff",
            "handoff_validation_errors": errors,
        }
    try:
        run_meaning_snapshot = build_meaning_context_v0(mission or {}, packet)
    except MeaningContextError as exc:
        return {
            "route": "chat",
            "answer": "現在のMissionとGoal Handoffから実行用のMeaning Contextを確定できないため、Runtimeを開始しません。",
            "events": [
                event(
                    "production_run_blocked",
                    reason="invalid_meaning_context",
                )
            ],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "runtime_prepared": False,
            "runtime_started": False,
            "production_run_error": "invalid_meaning_context",
            "meaning_context_validation_errors": [str(exc)],
        }
    existing_runtime = session.get("production_runtime_snapshot")
    existing_sandbox = (
        existing_runtime.get("sandbox_session")
        if isinstance(existing_runtime, Mapping)
        else None
    )
    resume_runtime = bool(
        isinstance(existing_runtime, Mapping)
        and isinstance(existing_sandbox, Mapping)
        and str(existing_sandbox.get("status") or "") == "ACTIVE"
    )
    before_hash = _canonical_handoff_hash(packet)
    existing_contract = session.get("production_run_contract")
    if isinstance(existing_contract, Mapping):
        contract_errors = validate_production_run_contract(
            existing_contract,
            mission=mission or {},
            handoff=packet,
            meaning_context=run_meaning_snapshot,
            handoff_canonical_hash=before_hash,
            runtime_snapshot=existing_runtime if resume_runtime else None,
        )
        if contract_errors:
            return {
                "route": "chat",
                "answer": "保存済みRun Contractと現在の正本が一致しないため、Runtimeを再開しません。",
                "events": [
                    event(
                        "production_run_blocked",
                        reason="run_contract_mismatch",
                    )
                ],
                "tool_used": False,
                "tools": [],
                "web_search": False,
                "research_saved": False,
                "executor": "local_agent",
                "cursor_connected": False,
                "memory": memory,
                "task_runtime": dict(existing_runtime)
                if isinstance(existing_runtime, Mapping)
                else None,
                "runtime_prepared": bool(existing_runtime),
                "runtime_started": bool(existing_runtime),
                "sandbox_started": False,
                "production_run_error": "run_contract_mismatch",
                "run_contract_validation_errors": contract_errors,
                "run_contract": dict(existing_contract),
            }
    elif resume_runtime:
        return {
            "route": "chat",
            "answer": "再開対象RuntimeにRun Contractが存在しないため、Runtimeを再開しません。",
            "events": [
                event("production_run_blocked", reason="missing_run_contract")
            ],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": dict(existing_runtime),
            "runtime_prepared": True,
            "runtime_started": True,
            "sandbox_started": False,
            "production_run_error": "missing_run_contract",
        }
    saved_runtime_identity = session.get("production_runtime_handoff_integrity")
    if resume_runtime and (
        not isinstance(saved_runtime_identity, Mapping)
        or str(saved_runtime_identity.get("handoff_id") or "")
        != str(packet.get("handoff_id") or "")
        or str(saved_runtime_identity.get("canonical_hash") or "") != before_hash
    ):
        return {
            "route": "chat",
            "answer": "保存済みRuntimeとGoal Handoffの同一性を確認できないため、再開していません。",
            "events": [event("production_run_blocked", reason="runtime_handoff_mismatch")],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": dict(existing_runtime),
            "runtime_prepared": True,
            "runtime_started": True,
            "sandbox_started": False,
            "production_run_error": "runtime_handoff_mismatch",
            "handoff_packet": packet,
            "production_status": "RUNTIME_CONTINUATION_BLOCKED",
            "model": model,
        }

    saved_acceptance = session.get("production_acceptance_evaluation")
    if isinstance(saved_acceptance, Mapping):
        acceptance_identity_matches = (
            str(saved_acceptance.get("handoff_id") or "")
            == str(packet.get("handoff_id") or "")
            and str(saved_acceptance.get("canonical_hash") or "") == before_hash
        )
        if not acceptance_identity_matches:
            return {
                "route": "chat",
                "answer": "保存済みAcceptance結果とGoal Handoffの同一性を確認できないため、実行を停止しました。",
                "events": [
                    event("production_run_blocked", reason="acceptance_handoff_mismatch")
                ],
                "tool_used": False,
                "tools": [],
                "web_search": False,
                "research_saved": False,
                "executor": "local_agent",
                "cursor_connected": False,
                "memory": memory,
                "task_runtime": dict(existing_runtime) if isinstance(existing_runtime, Mapping) else None,
                "runtime_prepared": bool(existing_runtime),
                "runtime_started": bool(existing_runtime),
                "sandbox_started": False,
                "task_step_executed": False,
                "production_run_error": "acceptance_handoff_mismatch",
                "handoff_packet": packet,
                "production_status": "GOAL_ACCEPTANCE_REUSE_BLOCKED",
                "model": model,
            }
        saved_result = dict(saved_acceptance.get("result") or {})
        saved_judgment = session.get("production_goal_acceptance_judgment")
        if isinstance(saved_judgment, Mapping):
            judgment_identity_matches = (
                str(saved_judgment.get("handoff_id") or "")
                == str(packet.get("handoff_id") or "")
                and str(saved_judgment.get("canonical_hash") or "") == before_hash
            )
            if not judgment_identity_matches:
                return {
                    "route": "chat",
                    "answer": "保存済みGoal判定とGoal Handoffの同一性を確認できないため、実行を停止しました。",
                    "events": [
                        event("production_run_blocked", reason="goal_judgment_handoff_mismatch")
                    ],
                    "tool_used": False,
                    "tools": [],
                    "web_search": False,
                    "research_saved": False,
                    "executor": "local_agent",
                    "cursor_connected": False,
                    "memory": memory,
                    "task_runtime": dict(existing_runtime) if isinstance(existing_runtime, Mapping) else None,
                    "runtime_prepared": bool(existing_runtime),
                    "runtime_started": bool(existing_runtime),
                    "sandbox_started": False,
                    "task_step_executed": False,
                    "production_run_error": "goal_judgment_handoff_mismatch",
                    "handoff_packet": packet,
                    "production_status": "GOAL_ACCEPTANCE_JUDGMENT_BLOCKED",
                    "model": model,
                }
            saved_reentry = saved_judgment.get("verification_reentry")
            if (
                isinstance(saved_reentry, Mapping)
                and str(saved_reentry.get("status") or "") == "VERIFICATION_REENTRY_CONTEXT_READY"
                and bool((saved_judgment.get("completion_eligibility") or {}).get("completion_eligible")) is False
                and resume_runtime
            ):
                from ai_tool.acceptance_meaning_completion import assess_acceptance_meaning_completion_eligibility
                from ai_tool.acceptance_meaning_verification_reentry import build_acceptance_meaning_verification_reentry
                from ai_tool.production_verification_acceptance import (
                    apply_acceptance_pass_to_runtime_goal,
                    evaluate_handoff_goal_acceptance,
                )
                from ai_tool.verification_only_execution import execute_verification_only_reentry

                reentry_orchestrator = ChatTaskOrchestrator(correlation_id, str((packet.get("goal") or {}).get("summary") or ""))
                try:
                    restore_orchestrator_from_runtime_snapshot(reentry_orchestrator, packet, existing_runtime)
                    reentry_execution = execute_verification_only_reentry(reentry_orchestrator, saved_reentry)
                except Exception as exc:
                    reentry_execution = {"status": "VERIFICATION_EXECUTION_FAILED", "reason": type(exc).__name__}
                if reentry_execution.get("status") != "VERIFICATION_EXECUTED":
                    return {
                        "route": "chat", "answer": "Verification-only 実行は完了しなかったため、Goalを未完了のまま停止しました。",
                        "events": [event("verification_only_stopped", status=reentry_execution.get("status"))],
                        "tool_used": False, "tools": [], "web_search": False, "research_saved": False,
                        "executor": "local_agent", "cursor_connected": False, "memory": memory,
                        "task_runtime": dict(existing_runtime), "runtime_prepared": True, "runtime_started": True,
                        "sandbox_started": False, "task_step_executed": False, "handoff_packet": packet,
                        "verification_reentry": dict(saved_reentry), "verification_execution": reentry_execution,
                        "production_status": "VERIFICATION_EXECUTION_GAP", "model": model,
                    }
                finalization_timing = _new_timing_breakdown()
                finalization_report = _runtime_status_report(
                    LoopStopReason.COMPLETED,
                    LoopCounters(
                        stagnation_limit=1,
                        same_failure_limit=1,
                        no_evidence_limit=1,
                    ),
                    reentry_orchestrator,
                )
                try:
                    finalization_response = _run_finalization_only(
                        chat_fn=chat_fn,
                        model=model,
                        messages=[],
                        runtime_status_report=finalization_report,
                        timing=finalization_timing,
                    )
                    final_answer = str(
                        getattr(
                            getattr(finalization_response, "message", None),
                            "content",
                            None,
                        )
                        or ""
                    )
                except Exception as exc:  # noqa: BLE001
                    return {
                        "route": "chat",
                        "answer": "Verification-only後のFinalizationに失敗したため、Acceptance再評価を停止しました。",
                        "events": [event("verification_finalization_stopped", reason=type(exc).__name__)],
                        "tool_used": False, "tools": [], "web_search": False, "research_saved": False,
                        "executor": "local_agent", "cursor_connected": False, "memory": memory,
                        "task_runtime": reentry_orchestrator.snapshot(), "runtime_prepared": True,
                        "runtime_started": True, "sandbox_started": False, "task_step_executed": False,
                        "handoff_packet": packet, "verification_reentry": dict(saved_reentry),
                        "verification_execution": reentry_execution,
                        "production_status": "VERIFICATION_EXECUTION_GAP", "model": model,
                    }
                if not final_answer.strip():
                    return {
                        "route": "chat",
                        "answer": "Verification-only後のFinalizationが空応答だったため、Acceptance再評価を停止しました。",
                        "events": [event("verification_finalization_stopped", reason="LLM_EMPTY_RESPONSE")],
                        "tool_used": False, "tools": [], "web_search": False, "research_saved": False,
                        "executor": "local_agent", "cursor_connected": False, "memory": memory,
                        "task_runtime": reentry_orchestrator.snapshot(), "runtime_prepared": True,
                        "runtime_started": True, "sandbox_started": False, "task_step_executed": False,
                        "handoff_packet": packet, "verification_reentry": dict(saved_reentry),
                        "verification_execution": reentry_execution,
                        "production_status": "VERIFICATION_EXECUTION_GAP", "model": model,
                    }
                refreshed = evaluate_handoff_goal_acceptance(
                    reentry_orchestrator,
                    final_answer=final_answer,
                    handoff_packet=packet,
                    mission=mission or {},
                )
                eligibility = assess_acceptance_meaning_completion_eligibility(refreshed)
                completed = apply_acceptance_pass_to_runtime_goal(
                    reentry_orchestrator, refreshed, completion_eligibility=eligibility
                )
                refreshed_reentry = build_acceptance_meaning_verification_reentry(
                    refreshed, handoff_packet=packet, mission=mission, runtime=reentry_orchestrator.runtime
                )
                snapshot = reentry_orchestrator.snapshot()
                judgment = {
                    "handoff_id": packet.get("handoff_id"), "canonical_hash": before_hash,
                    "acceptance_status": refreshed.get("status"), "goal_id": "G1",
                    "goal_completed": completed, "completion_eligibility": eligibility,
                    "verification_reentry": refreshed_reentry,
                }
                session["production_runtime_snapshot"] = snapshot
                session["production_acceptance_evaluation"] = {"handoff_id": packet.get("handoff_id"), "canonical_hash": before_hash, "result": refreshed}
                session["production_goal_acceptance_judgment"] = judgment
                return {
                    "route": "chat", "answer": "Verification-only 実行後にAcceptanceとGoal判定を再評価して停止しました。",
                    "events": [event("verification_only_re_evaluated", handoff_id=packet.get("handoff_id"), goal_completed=completed)],
                    "tool_used": False, "tools": [], "web_search": False, "research_saved": False,
                    "executor": "local_agent", "cursor_connected": False, "memory": memory,
                    "task_runtime": snapshot, "runtime_prepared": True, "runtime_started": True,
                    "sandbox_started": False, "task_step_executed": False, "handoff_packet": packet,
                    "acceptance_ready": True, "acceptance_evaluated": True, "acceptance_reused": False,
                    "acceptance_result": refreshed, "goal_acceptance_judgment": judgment,
                    "goal_judgment_reused": False, "verification_reentry": refreshed_reentry,
                    "verification_execution": reentry_execution,
                    "production_status": "GOAL_ACCEPTANCE_JUDGED" if completed else "VERIFICATION_EXECUTION_GAP",
                    "model": model,
                }
            return {
                "route": "chat",
                "answer": "このGoal HandoffへのAcceptance判定は適用済みです。保存済みRuntime Goal状態を返して停止しました。",
                "events": [
                    event(
                        "production_goal_acceptance_judgment_reused",
                        handoff_id=packet.get("handoff_id"),
                    )
                ],
                "tool_used": False,
                "tools": [],
                "web_search": False,
                "research_saved": False,
                "executor": "local_agent",
                "cursor_connected": False,
                "memory": memory,
                "task_runtime": dict(existing_runtime) if isinstance(existing_runtime, Mapping) else None,
                "runtime_prepared": bool(existing_runtime),
                "runtime_started": bool(existing_runtime),
                "sandbox_started": False,
                "task_step_executed": False,
                "handoff_packet": packet,
                "acceptance_ready": True,
                "acceptance_evaluated": True,
                "acceptance_reused": True,
                "acceptance_result": saved_result,
                "goal_acceptance_judgment": dict(saved_judgment),
                "goal_judgment_reused": True,
                "verification_reentry": dict(saved_judgment.get("verification_reentry") or {}),
                "production_status": (
                    "VERIFICATION_EXECUTION_GAP"
                    if isinstance(saved_judgment.get("verification_reentry"), Mapping)
                    and str(saved_judgment["verification_reentry"].get("status") or "")
                    in {"VERIFICATION_REENTRY_CONTEXT_READY", "VERIFICATION_REENTRY_UNRESOLVED"}
                    else "GOAL_ACCEPTANCE_JUDGED"
                ),
                "model": model,
            }
        if not resume_runtime:
            return {
                "route": "chat",
                "answer": "Acceptance結果を適用できるRuntime状態がないため、実行を停止しました。",
                "events": [event("production_run_blocked", reason="missing_runtime_for_goal_judgment")],
                "tool_used": False,
                "tools": [],
                "web_search": False,
                "research_saved": False,
                "executor": "local_agent",
                "cursor_connected": False,
                "memory": memory,
                "task_runtime": None,
                "runtime_prepared": False,
                "runtime_started": False,
                "sandbox_started": False,
                "task_step_executed": False,
                "production_run_error": "missing_runtime_for_goal_judgment",
                "handoff_packet": packet,
                "production_status": "GOAL_ACCEPTANCE_JUDGMENT_BLOCKED",
                "model": model,
            }
        original_request = str((packet.get("goal") or {}).get("original_request_excerpt") or "").strip()
        judgment_orchestrator = ChatTaskOrchestrator(
            correlation_id,
            original_request or str((packet.get("goal") or {}).get("summary") or ""),
        )
        try:
            restore_orchestrator_from_runtime_snapshot(
                judgment_orchestrator,
                packet,
                existing_runtime,
            )
        except Exception as exc:
            return {
                "route": "chat",
                "answer": "Acceptance結果を適用するRuntime状態の復元に失敗したため、実行を停止しました。",
                "events": [
                    event(
                        "production_run_blocked",
                        reason="goal_judgment_runtime_restore_failed",
                        error_type=type(exc).__name__,
                    )
                ],
                "tool_used": False,
                "tools": [],
                "web_search": False,
                "research_saved": False,
                "executor": "local_agent",
                "cursor_connected": False,
                "memory": memory,
                "task_runtime": dict(existing_runtime),
                "runtime_prepared": True,
                "runtime_started": True,
                "sandbox_started": False,
                "task_step_executed": False,
                "production_run_error": "goal_judgment_runtime_restore_failed",
                "handoff_packet": packet,
                "production_status": "GOAL_ACCEPTANCE_JUDGMENT_BLOCKED",
                "model": model,
            }
        from ai_tool.production_verification_acceptance import (
            apply_acceptance_pass_to_runtime_goal,
        )
        from ai_tool.acceptance_meaning_completion import (
            assess_acceptance_meaning_completion_eligibility,
        )
        from ai_tool.acceptance_meaning_verification_reentry import (
            build_acceptance_meaning_verification_reentry,
        )

        completion_eligibility = assess_acceptance_meaning_completion_eligibility(
            saved_result
        )
        goal_completed = apply_acceptance_pass_to_runtime_goal(
            judgment_orchestrator,
            saved_result,
            completion_eligibility=completion_eligibility,
        )
        verification_reentry = build_acceptance_meaning_verification_reentry(
            saved_result,
            handoff_packet=packet,
            mission=mission,
            runtime=judgment_orchestrator.runtime,
        )
        verification_execution_gap = str(verification_reentry.get("status") or "") in {
            "VERIFICATION_REENTRY_CONTEXT_READY",
            "VERIFICATION_REENTRY_UNRESOLVED",
        }
        judgment_snapshot = judgment_orchestrator.snapshot()
        judgment = {
            "handoff_id": packet.get("handoff_id"),
            "canonical_hash": before_hash,
            "acceptance_status": saved_result.get("status"),
            "goal_id": "G1",
            "goal_completed": goal_completed,
            "completion_eligibility": completion_eligibility,
            "verification_reentry": verification_reentry,
        }
        session["production_runtime_snapshot"] = judgment_snapshot
        session["production_goal_acceptance_judgment"] = judgment
        return {
            "route": "chat",
            "answer": "保存済みAcceptance結果をRuntime Goalへ適用し、判定状態を保存して停止しました。",
            "events": [
                event(
                    "production_goal_acceptance_judged",
                    handoff_id=packet.get("handoff_id"),
                    acceptance_status=saved_result.get("status"),
                    goal_completed=goal_completed,
                    completion_eligible=completion_eligibility.get("completion_eligible"),
                )
            ],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": judgment_snapshot,
            "runtime_prepared": True,
            "runtime_started": True,
            "sandbox_started": False,
            "runtime_resumed": False,
            "task_step_executed": False,
            "handoff_packet": packet,
            "acceptance_ready": True,
            "acceptance_evaluated": True,
            "acceptance_reused": True,
            "acceptance_result": saved_result,
            "goal_acceptance_judgment": judgment,
            "goal_judgment_reused": False,
            "verification_reentry": verification_reentry,
            "production_status": (
                "VERIFICATION_EXECUTION_GAP"
                if verification_execution_gap
                else "GOAL_ACCEPTANCE_JUDGED"
            ),
            "model": model,
        }

    original_request = str((packet.get("goal") or {}).get("original_request_excerpt") or "").strip()
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        original_request or str((packet.get("goal") or {}).get("summary") or ""),
    )
    mission_id = str(session.get("last_mission_id") or "").strip()
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id or None,
        new_execution=True,
    )
    restore_mission_clarifications(orchestrator)
    after_hash = _canonical_handoff_hash(packet)
    immutable_fields = ("handoff_id", "goal", "scope", "acceptance_criteria", "implementation_tasks")
    immutable_equal = all(packet.get(key) == saved.get(key) for key in immutable_fields)
    try:
        if resume_runtime:
            restore_orchestrator_from_runtime_snapshot(
                orchestrator,
                packet,
                existing_runtime,
            )
            sandbox = orchestrator.runtime.sandbox_session
        else:
            prepare_orchestrator_from_handoff(orchestrator, packet)
            if not isinstance(existing_contract, Mapping):
                existing_contract = build_production_run_contract(
                    started_execution_id=str(orchestrator.execution_id or ""),
                    mission=mission or {},
                    handoff=packet,
                    meaning_context=run_meaning_snapshot,
                    starting_task_id=str(orchestrator.current_task_id or ""),
                    handoff_canonical_hash=before_hash,
                )
                session["production_run_contract"] = existing_contract
            sandbox = orchestrator.runtime.start_dedicated_sandbox(
                DEVELOPMENT_WORKTREE,
                resolve_configured_sandbox_parent(DEVELOPMENT_WORKTREE),
            )
    except Exception as exc:
        reason = "runtime_resume_validation_failed" if resume_runtime else "sandbox_bootstrap_failed"
        return {
            "route": "chat",
            "answer": "Runtimeの安全な開始または再開に失敗したため、Taskを実行していません。",
            "events": [
                event(
                    "production_run_blocked",
                    reason=reason,
                    error_type=type(exc).__name__,
                )
            ],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": orchestrator.snapshot(),
            "runtime_prepared": True,
            "runtime_started": False,
            "sandbox_started": False,
            "production_run_error": reason,
            "handoff_packet": packet,
            "run_meaning_snapshot": run_meaning_snapshot,
            "run_contract": dict(existing_contract or {}),
            "handoff_integrity": {
                "handoff_id": packet.get("handoff_id"),
                "saved_canonical_hash": before_hash,
                "runtime_input_canonical_hash": after_hash,
                "canonical_hash_equal": before_hash == after_hash,
                "immutable_fields": list(immutable_fields),
                "immutable_fields_equal": immutable_equal,
            },
            "production_status": "RUNTIME_BLOCKED_BEFORE_START",
            "mission_memory": {"mission_id": mission_id or None},
            "model": model,
        }
    action_count_before = len(orchestrator.runtime.actions)
    task_id_before = orchestrator.current_task_id
    execution_result = _chat_turn(
        original_request or orchestrator.request,
        session,
        chat_fn=chat_fn,
        model=model,
        memory=memory,
        correlation_id=correlation_id,
        orchestrator=orchestrator,
        max_tool_calls_this_turn=1,
    )
    from ai_tool.production_verification_acceptance import (
        advance_runnable_handoff_task,
        assess_handoff_acceptance_readiness,
    )

    task_completed = orchestrator.runtime.evaluate_task_from_evidence(task_id_before)
    if task_completed and orchestrator.current_task_id == task_id_before:
        advance_runnable_handoff_task(orchestrator)
    next_task_id = (
        orchestrator.current_task_id
        if task_completed and orchestrator.current_task_id != task_id_before
        else None
    )
    completed_task = orchestrator.runtime.tasks[task_id_before]
    completion_evidence_ids = list(
        dict.fromkeys(
            evidence_id
            for condition in completed_task.completion_conditions
            if completed_task.condition_status.get(condition) == "SATISFIED"
            for evidence_id in completed_task.condition_evidence.get(condition, [])
        )
    )
    missing_conditions = [
        condition
        for condition in completed_task.completion_conditions
        if completed_task.condition_status.get(condition) != "SATISFIED"
    ]
    runtime_snapshot = orchestrator.snapshot()
    acceptance_readiness = assess_handoff_acceptance_readiness(orchestrator)
    session["production_runtime_snapshot"] = runtime_snapshot
    session["production_acceptance_readiness"] = acceptance_readiness
    session["production_runtime_handoff_integrity"] = {
        "handoff_id": packet.get("handoff_id"),
        "canonical_hash": before_hash,
    }
    task_step_executed = len(runtime_snapshot.get("actions") or []) == action_count_before + 1
    acceptance_result = None
    if acceptance_readiness["acceptance_ready"]:
        from ai_tool.production_verification_acceptance import (
            evaluate_handoff_goal_acceptance,
        )

        lifecycle = execution_result.get("final_llm_lifecycle") or {}
        llm_response_received = (
            bool(lifecycle.get("final_llm_response_received"))
            if isinstance(lifecycle, Mapping)
            else None
        )
        acceptance_result = evaluate_handoff_goal_acceptance(
            orchestrator,
            final_answer=str(execution_result.get("answer") or ""),
            llm_response_received=llm_response_received,
            handoff_packet=packet,
            mission=mission or {},
        )
        session["production_acceptance_evaluation"] = {
            "handoff_id": packet.get("handoff_id"),
            "canonical_hash": before_hash,
            "result": acceptance_result,
        }
    execution_result.update(
        {
            "events": [
            event(
                (
                    "production_run_runtime_resumed"
                    if resume_runtime
                    else "production_run_sandbox_started"
                ),
                handoff_id=packet.get("handoff_id"),
                sandbox_session_id=sandbox.session_id,
                runtime_started=True,
            ),
            *(execution_result.get("events") or []),
        ],
            "task_runtime": runtime_snapshot,
            "runtime_prepared": True,
            "runtime_started": True,
            "sandbox_started": not resume_runtime,
            "runtime_resumed": resume_runtime,
            "handoff_packet": packet,
            "run_meaning_snapshot": run_meaning_snapshot,
            "run_contract": dict(existing_contract or {}),
            "handoff_integrity": {
            "handoff_id": packet.get("handoff_id"),
            "saved_canonical_hash": before_hash,
            "runtime_input_canonical_hash": after_hash,
            "canonical_hash_equal": before_hash == after_hash,
            "immutable_fields": list(immutable_fields),
            "immutable_fields_equal": immutable_equal,
        },
            "task_step_executed": task_step_executed,
            "task_completion_boundary": {
                "task_id": task_id_before,
                "completed": task_completed,
                "completion_evidence_ids": completion_evidence_ids,
                "missing_conditions": missing_conditions,
                "next_task_id": next_task_id,
                "stopped_before_next_task_execution": True,
            },
            "acceptance_readiness": acceptance_readiness,
            "acceptance_ready": acceptance_readiness["acceptance_ready"],
            "acceptance_evaluated": acceptance_result is not None,
            "acceptance_reused": False,
            "acceptance_result": acceptance_result,
            "production_status": (
                "GOAL_ACCEPTANCE_EVALUATED"
                if acceptance_result is not None
                else "RUNTIME_TASK_COMPLETED_NEXT_READY"
                if task_completed and next_task_id
                else "RUNTIME_TASK_COMPLETED"
                if task_completed
                else "RUNTIME_FIRST_TASK_STEP_FINISHED"
                if task_step_executed
                else "RUNTIME_BLOCKED_BEFORE_TASK_ACTION"
            ),
        }
    )
    if acceptance_result is not None:
        execution_result["events"].append(
            event(
                "production_goal_acceptance_evaluated",
                handoff_id=packet.get("handoff_id"),
                status=acceptance_result.get("status"),
            )
        )
    return execution_result


def _new_mission_record(
    mission_id: str,
    bundle: RequirementResolutionBundle,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": schema_version(),
        "mission_id": mission_id,
        "explicit_conditions": [],
        "explicit_constraints": [],
        "user_confirmed_supplements": [],
        **bundle.as_mission_fields(),
    }
    return merge_mission_requirement_fields(record, bundle)


def _attach_requirement_contract(orchestrator: ChatTaskOrchestrator, bundle: RequirementResolutionBundle) -> None:
    orchestrator.structured_requirements = [
        row.as_dict() for row in bundle.structured_requirements
    ]
    orchestrator.requirement_resolution_phase = bundle.requirement_resolution_phase
    _, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    orchestrator.projected_explicit_constraints = list(constraints)
    sync_canonical_requirement_projection(orchestrator)


def _requirement_resolution_blocked_turn(
    *,
    correlation_id: str,
    memory: dict[str, Any],
    model: str,
    bundle: RequirementResolutionBundle,
    mission_id: str,
    launched: dict[str, Any],
) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "route": "chat",
        "answer": launched["formatted"],
        "events": [
            event(
                "requirement_resolution_grill_launched",
                mission_id=mission_id,
                phase=bundle.requirement_resolution_phase,
                pending_requirement_id=launched.get("pending_requirement_id"),
            )
        ],
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": None,
        "awaiting_requirement_resolution": True,
        "requirement_resolution_grill": launched.get("record"),
        "requirement_resolution_state": launched.get("state"),
        "requirement_resolution": bundle.as_mission_fields(),
        "mission_memory": {"mission_id": mission_id},
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-requirement-resolution",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(launched["formatted"]),
            "final_llm_response_empty": not bool(str(launched["formatted"]).strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
        "correlation_id": correlation_id,
    }


def _production_grill_phase1_turn(
    *,
    correlation_id: str,
    memory: dict[str, Any],
    model: str,
    mission_id: str,
    original_request: str,
    step: Mapping[str, Any],
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    awaiting = str(step.get("status") or "") == "awaiting_human"
    contract = dict(step.get("question_contract") or {})
    if awaiting:
        options = [str(row.get("label") or "") for row in contract.get("options") or [] if isinstance(row, Mapping)]
        answer = str(contract.get("question") or "")
        if options:
            answer += "\n\n" + "\n".join(f"- {item}" for item in options)
    else:
        answer = "Specification and Goal Handoff are ready."
    timestamp = now_iso()
    result = {
        "route": "chat",
        "answer": answer,
        "events": [event("production_grill_me_awaiting_human" if awaiting else "production_grill_me_aligned", mission_id=mission_id)],
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": None,
        "mission_memory": {"mission_id": mission_id},
        "awaiting_production_grill_me": awaiting,
        "production_grill_me": contract if awaiting else None,
        "production_grill_me_state": (
            {
                "mission_id": mission_id,
                "original_request": original_request,
                "transcript": list(step.get("transcript") or []),
                "active_contract": contract,
            }
            if awaiting
            else None
        ),
        "aligned_spec": dict(step.get("aligned_spec") or {}) if not awaiting else None,
        "generated_aligned_spec": dict(step.get("generated_aligned_spec") or {}) if not awaiting else None,
        "semantic_preservation": dict(step.get("semantic_preservation") or {}) if not awaiting else None,
        "ambiguity_report": dict(step.get("ambiguity_report") or {}),
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-production-grill-me",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": not bool(answer.strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
    }
    if not awaiting:
        pipeline = run_production_spec_handoff_pipeline(
            mission_id=mission_id,
            initial_request=original_request,
            aligned_spec=result["aligned_spec"] or {},
            semantic_preservation=result["semantic_preservation"] or {},
            chat_fn=chat_fn,
            model=model,
        )
        result.update(
            {
                "production_status": pipeline.get("production_status"),
                "dev_skill_pipeline": pipeline,
                "prd": pipeline.get("prd"),
                "tech_spec": pipeline.get("tech_spec"),
                "plan": pipeline.get("plan"),
                "handoff_packet": pipeline.get("handoff_packet"),
                "semantic_trace": pipeline.get("semantic_trace"),
                "runtime_started": False,
            }
        )
        mission = MissionMemoryStore.from_default().get_mission(mission_id) or {}
        meaning_context = build_meaning_context_v0(
            mission,
            result["handoff_packet"] or {},
        )
        result["meaning_context"] = meaning_context
        result["meaning_context_status"] = meaning_context["status"]
        result["events"].append(event("production_spec_handoff_ready", mission_id=mission_id))
        result["events"].append(
            event(
                "production_meaning_context_saved",
                mission_id=mission_id,
                handoff_id=(result["handoff_packet"] or {}).get("handoff_id"),
                status=meaning_context["status"],
            )
        )
    return result


def _production_grill_resume_turn(
    user_text: str,
    packet: Mapping[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    chat_fn: ChatFn | None,
) -> dict[str, Any]:
    store = MissionMemoryStore.from_default()
    mission, resumed = apply_production_grill_human_answer(packet, user_text, store=store)
    step = run_production_grill_phase1(
        mission=mission,
        transcript=resumed.get("transcript") or [],
        chat_fn=chat_fn,
        model=model,
        store=store,
    )
    return _production_grill_phase1_turn(
        correlation_id=correlation_id,
        memory=memory,
        model=model,
        mission_id=str(packet.get("mission_id") or ""),
        original_request=str(packet.get("original_request") or mission.get("original_goal") or ""),
        step=step,
        chat_fn=chat_fn,
    )


def _semantic_revalidation_blocked_turn(
    *,
    correlation_id: str,
    memory: dict[str, Any],
    model: str,
    bundle: RequirementResolutionBundle,
    mission_id: str,
    sem_result: SemanticRevalidationResult,
) -> dict[str, Any]:
    answer = semantic_revalidation_blocked_answer(sem_result)
    timestamp = now_iso()
    return {
        "route": "chat",
        "answer": answer,
        "events": [
            event(
                "requirement_semantic_revalidation_blocked",
                mission_id=mission_id,
                decision=sem_result.decision,
                reason_codes=list(sem_result.reason_codes),
            )
        ],
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": None,
        "awaiting_semantic_revalidation": sem_result.decision == "NEED_HUMAN",
        "semantic_revalidation": sem_result.as_dict(),
        "requirement_resolution": bundle.as_mission_fields(),
        "mission_memory": {"mission_id": mission_id},
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-semantic-revalidation",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": not bool(answer.strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
        "correlation_id": correlation_id,
    }


def _requirement_resolution_resume_turn(
    user_text: str,
    packet: dict[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    session: dict[str, Any],
    chat_fn: ChatFn | None,
    timing: dict[str, Any],
    local_review_enabled: bool,
    review_chat_fn: ChatFn | None,
    pipeline_observer: PipelineObserver | None,
) -> dict[str, Any]:
    store = MissionMemoryStore.from_default()
    mission_id = str(packet.get("mission_id") or "")
    mission = store.get_mission(mission_id) or {}
    mission, bundle = apply_requirement_resolution_grill_answer(mission, packet, user_text)
    store.put_mission(mission)
    events = [
        event(
            "requirement_resolution_answer_applied",
            mission_id=mission_id,
            phase=bundle.requirement_resolution_phase,
        )
    ]
    if requirements_block_implementation_entry(
        bundle.requirement_resolution_phase,
        bundle.structured_requirements,
    ):
        launched = launch_requirement_resolution_grill(
            mission_id=mission_id,
            original_request=str(packet.get("original_request") or mission.get("original_goal") or ""),
            bundle=bundle,
        )
        if launched is None:
            return {
                "route": "chat",
                "answer": "要件解決を続行できませんでした。",
                "events": events,
                "tool_used": False,
                "tools": [],
                "memory": memory,
                "correlation_id": correlation_id,
            }
        return _requirement_resolution_blocked_turn(
            correlation_id=correlation_id,
            memory=memory,
            model=model,
            bundle=bundle,
            mission_id=mission_id,
            launched=launched,
        )
    original_request = str(packet.get("original_request") or mission.get("original_goal") or "")
    events.append(
        event(
            "requirement_resolution_closed",
            mission_id=mission_id,
            phase=PHASE_REQUIREMENTS_RESOLVED,
        )
    )
    if session.get("awaiting_goal_continuation"):
        timestamp = now_iso()
        return {
            "route": "chat",
            "answer": "要件解決が完了しました。",
            "events": events,
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "awaiting_requirement_resolution": False,
            "requirement_resolution_state": None,
            "requirement_resolution": bundle.as_mission_fields(),
            "mission_memory": {"mission_id": mission_id},
            "model": model,
            "correlation_id": correlation_id,
            "final_llm_lifecycle": {
                "llm_request_id": f"{correlation_id}-requirement-resolution",
                "final_llm_request_started": False,
                "final_llm_request_started_at": None,
                "final_llm_response_received": True,
                "final_llm_response_received_at": timestamp,
                "final_llm_response_length": len("要件解決が完了しました。"),
                "final_llm_response_empty": False,
                "final_response_accepted": True,
                "final_response_discarded": False,
                "late_response_received": False,
                "turn_closed_before_response": False,
                "empty_reason": None,
            },
        }
    concept_resolution = detect_unknown_concept(original_request, known_identifiers=set())
    adopted, constraints = project_to_runtime_adoption(bundle.structured_requirements)
    if not adopted:
        adopted = ["relevant evidence observed"]
    orchestrator = ChatTaskOrchestrator(
        correlation_id,
        original_request,
        completion_conditions=adopted,
        concept_resolution=concept_resolution,
    )
    orchestrator.user_explicit_conditions = list(adopted)
    _attach_requirement_contract(orchestrator, bundle)
    orchestrator.projected_explicit_constraints = list(constraints)
    orchestrator.initialize()
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id,
        new_execution=True,
    )
    restore_mission_clarifications(orchestrator)
    step = run_production_grill_phase1(
        orchestrator=orchestrator,
        chat_fn=chat_fn,
        model=model,
        store=store,
    )
    phase1_result = _production_grill_phase1_turn(
        correlation_id=correlation_id,
        memory=memory,
        model=model,
        mission_id=mission_id,
        original_request=original_request,
        step=step,
        chat_fn=chat_fn,
    )
    phase1_result["events"] = events + list(phase1_result.get("events") or [])
    phase1_result["awaiting_requirement_resolution"] = False
    phase1_result["requirement_resolution_state"] = None
    phase1_result["requirement_resolution"] = bundle.as_mission_fields()
    return phase1_result


def _boundary_grill_resume_turn(
    user_text: str,
    packet: dict[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    session: dict[str, Any] | None = None,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    """Apply Boundary Grill Human answer, re-run Router, and continue or re-ask."""
    contract = dict(packet.get("active_contract") or {})
    orchestrator = restore_orchestrator_from_boundary_grill(correlation_id, packet)
    bind_execution_identity(
        orchestrator,
        resume_mission_id=str(packet.get("mission_id") or "") or None,
        new_execution=True,
    )
    prepared = prepare_boundary_grill_answer(orchestrator, user_text, contract)
    events = [
        event(
            "boundary_grill_answer_proposed",
            applied=False,
            conflict_class=prepared.get("conflict_class"),
            decision_key=prepared.get("decision_key"),
            proposed_label=(prepared.get("proposed") or {}).get("text"),
            prior_label=(prepared.get("prior") or {}).get("text") if prepared.get("prior") else None,
        )
    ]
    if prepared.get("needs_confirmation"):
        prior = dict(prepared.get("prior") or {})
        proposed = dict(prepared.get("proposed") or {})
        launched = launch_decision_change_confirmation(
            orchestrator,
            resume_packet=packet,
            pending_application={
                "consumer": "boundary_grill",
                "contract": contract,
                "proposed": proposed,
                "prior": prior,
                "prior_decision_id": prepared.get("prior_decision_id"),
                "decision_key": prepared.get("decision_key"),
                "conflict_class": prepared.get("conflict_class"),
            },
            prior=prior,
            proposed=proposed,
        )
        events.append(
            event(
                "decision_change_conflict_detected",
                decision_key=prepared.get("decision_key"),
                prior_decision_id=prepared.get("prior_decision_id"),
                conflict_class=prepared.get("conflict_class"),
            )
        )
        events.append(
            event(
                "decision_change_confirmation_launched",
                decision_key=prepared.get("decision_key"),
                prior_label=prior.get("text"),
                proposed_label=proposed.get("text"),
            )
        )
        recorded = persist_chat_execution(
            orchestrator,
            stop_reason="DECISION_CHANGE_CONFIRMATION",
            determined=True,
            answer=launched["formatted"],
            correlation_id=correlation_id,
        )
        events.append(
            event(
                "mission_memory",
                status="saved",
                mission_id=recorded.get("mission_id"),
                execution_id=recorded.get("execution_id"),
            )
        )
        timestamp = now_iso()
        return {
            "route": "chat",
            "answer": launched["formatted"],
            "events": events,
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": orchestrator.snapshot(),
            "awaiting_boundary_grill": False,
            "boundary_grill": None,
            "boundary_grill_state": None,
            "awaiting_decision_change_confirmation": True,
            "decision_change_confirmation_state": launched["state"],
            "mission_memory": recorded,
            "final_llm_lifecycle": {
                "llm_request_id": f"{correlation_id}-decision-change-launched",
                "final_llm_request_started": False,
                "final_llm_request_started_at": None,
                "final_llm_response_received": True,
                "final_llm_response_received_at": timestamp,
                "final_llm_response_length": len(launched["formatted"]),
                "final_llm_response_empty": not bool(launched["formatted"].strip()),
                "final_response_accepted": True,
                "final_response_discarded": False,
                "late_response_received": False,
                "turn_closed_before_response": False,
                "empty_reason": None,
            },
            "model": model,
        }
    applied = _apply_prepared_boundary_grill_answer(
        orchestrator,
        user_text,
        contract,
        prepared,
    )
    events.append(
        event(
            "boundary_grill_answer_applied",
            applied=applied.get("applied"),
            duplicate=applied.get("duplicate"),
            dimension=applied.get("dimension"),
            decision_id=applied.get("decision_id"),
            decision_key=applied.get("decision_key"),
            selected_label=applied.get("selected_label"),
            open_dimensions=applied.get("open_dimensions"),
        )
    )
    return _boundary_grill_post_apply_reroute(
        orchestrator,
        events=events,
        correlation_id=correlation_id,
        memory=memory,
        model=model,
        applied=applied,
        stop_reason="BOUNDARY_GRILL_ANSWERED",
        lifecycle_suffix="boundary-grill-resume",
        session=session,
        chat_fn=chat_fn,
    )


def _decision_change_confirmation_resume_turn(
    user_text: str,
    packet: dict[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
    session: dict[str, Any] | None = None,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    """Apply confirm / keep / defer for a pending Decision change."""
    pending = dict(packet.get("pending_application") or {})
    resume_packet = dict(packet.get("resume_packet") or {})
    contract = dict(pending.get("contract") or resume_packet.get("active_contract") or {})
    orchestrator = restore_orchestrator_from_boundary_grill(correlation_id, resume_packet)
    bind_execution_identity(
        orchestrator,
        resume_mission_id=str(packet.get("mission_id") or resume_packet.get("mission_id") or "") or None,
        new_execution=True,
    )
    choice = interpret_decision_change_answer(user_text)
    events = [
        event(
            "decision_change_answer",
            choice=choice,
            decision_key=pending.get("decision_key"),
        )
    ]
    if choice == OPTION_DEFER_CHANGE:
        recorded = persist_chat_execution(
            orchestrator,
            stop_reason="DECISION_CHANGE_DEFERRED",
            determined=True,
            answer="Decision 変更は保留しました。以前の判断を維持します。",
            correlation_id=correlation_id,
        )
        events.append(
            event(
                "decision_change_deferred",
                decision_key=pending.get("decision_key"),
            )
        )
        events.append(
            event(
                "mission_memory",
                status="saved",
                mission_id=recorded.get("mission_id"),
                execution_id=recorded.get("execution_id"),
            )
        )
        timestamp = now_iso()
        return {
            "route": "chat",
            "answer": "Decision 変更は保留しました。以前の判断を維持します。",
            "events": events,
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": orchestrator.snapshot(),
            "awaiting_decision_change_confirmation": True,
            "decision_change_confirmation_state": packet,
            "awaiting_boundary_grill": False,
            "boundary_grill": None,
            "boundary_grill_state": None,
            "mission_memory": recorded,
            "final_llm_lifecycle": {
                "llm_request_id": f"{correlation_id}-decision-change-deferred",
                "final_llm_request_started": False,
                "final_llm_request_started_at": None,
                "final_llm_response_received": True,
                "final_llm_response_received_at": timestamp,
                "final_llm_response_length": 0,
                "final_llm_response_empty": False,
                "final_response_accepted": True,
                "final_response_discarded": False,
                "late_response_received": False,
                "turn_closed_before_response": False,
                "empty_reason": None,
            },
            "model": model,
        }
    if choice == OPTION_KEEP_PRIOR:
        events.append(
            event(
                "decision_change_rejected",
                decision_key=pending.get("decision_key"),
                prior_decision_id=pending.get("prior_decision_id"),
            )
        )
        return _boundary_grill_post_apply_reroute(
            orchestrator,
            events=events,
            correlation_id=correlation_id,
            memory=memory,
            model=model,
            applied={"applied": False, "duplicate": True},
            stop_reason="DECISION_CHANGE_REJECTED",
            lifecycle_suffix="decision-change-rejected",
            session=session,
            chat_fn=chat_fn,
        )
    proposed = dict(pending.get("proposed") or {})
    prior_decision_id = str(pending.get("prior_decision_id") or "")
    events.append(
        event(
            "decision_change_confirmed",
            decision_key=pending.get("decision_key"),
            prior_decision_id=prior_decision_id,
        )
    )
    applied = apply_boundary_grill_answer(
        orchestrator,
        "",
        contract,
        proposed=proposed,
        supersede_prior_id=prior_decision_id or None,
    )
    events.append(
        event(
            "decision_superseded",
            prior_decision_id=prior_decision_id,
            new_decision_id=applied.get("decision_id"),
            decision_key=applied.get("decision_key"),
        )
    )
    events.append(
        event(
            "boundary_grill_answer_applied",
            applied=applied.get("applied"),
            dimension=applied.get("dimension"),
            decision_id=applied.get("decision_id"),
            decision_key=applied.get("decision_key"),
            selected_label=applied.get("selected_label"),
            open_dimensions=applied.get("open_dimensions"),
            via_decision_change_confirmation=True,
        )
    )
    return _boundary_grill_post_apply_reroute(
        orchestrator,
        events=events,
        correlation_id=correlation_id,
        memory=memory,
        model=model,
        applied=applied,
        stop_reason="DECISION_CHANGE_CONFIRMED",
        lifecycle_suffix="decision-change-confirmed",
        session=session,
        chat_fn=chat_fn,
    )


def _goal_completion_resume_turn(
    user_text: str,
    packet: dict[str, Any],
    *,
    correlation_id: str,
    model: str,
    memory: dict[str, Any],
) -> dict[str, Any]:
    """Apply a Human Goal-meaning answer to the same mission. No tools, no LLM."""
    mission_id = str(packet.get("mission_id") or "")
    original = str(packet.get("original_request") or "")
    judgment = interpret_goal_completion_answer(
        user_text,
        case=str(packet.get("case") or ""),
    )
    answer = format_goal_completion_judgment(judgment)
    events = [
        event(
            "goal_completion_resume",
            mission_id=mission_id,
            status=judgment.get("status"),
            reason=judgment.get("reason"),
        )
    ]
    orchestrator = ChatTaskOrchestrator(correlation_id, original)
    bind_execution_identity(
        orchestrator,
        resume_mission_id=mission_id or None,
        new_execution=True,
    )
    restore_mission_clarifications(orchestrator)
    from ai_tool.mission_memory.task_runtime import (
        apply_orchestrator_completion_runtime,
        resolve_canonical_completion_runtime,
    )

    completion_runtime = resolve_canonical_completion_runtime(
        mission_id,
        packet.get("completion_runtime") or {},
    )
    apply_orchestrator_completion_runtime(
        orchestrator,
        completion_runtime,
        replace_graph=ChatTaskOrchestrator.completion_runtime_requires_graph_restore(
            completion_runtime
        ),
    )
    orchestrator.goal_completion_consumed = True
    persist_kwargs: dict[str, Any] = {
        "stop_reason": (
            "GOAL_COMPLETION_JUDGED"
            if judgment.get("status") == "judged"
            else "GOAL_COMPLETION_UNSUPPORTED"
        ),
        "determined": True,
        "answer": answer,
        "correlation_id": correlation_id,
        "extra_evidence_refs": [
            str(item) for item in (packet.get("evidence_refs") or []) if str(item)
        ],
    }
    if judgment.get("status") == "judged":
        orchestrator.goal_completion_supplements = [
            {"text": str(judgment.get("supplement_text") or "")}
        ]
        orchestrator.user_explicit_conditions = [
            str(judgment.get("supplement_text") or "")
        ]
        persist_kwargs["execution_end_state"] = judgment.get("execution_end_state")
        persist_kwargs["goal_achievement_performed"] = True
        persist_kwargs["goal_achievement_result"] = judgment.get(
            "goal_achievement_result"
        )
    synthesis = orchestrator.finish(answer, allow_completion=True)
    recorded = persist_chat_execution(orchestrator, **persist_kwargs)
    events.append(
        event(
            "mission_memory",
            status="saved",
            mission_id=recorded.get("mission_id"),
            execution_id=recorded.get("execution_id"),
        )
    )
    timestamp = now_iso()
    return {
        "route": "chat",
        "answer": answer,
        "events": events,
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "local_agent",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": orchestrator.snapshot(),
        "final_synthesis": synthesis,
        "goal_completion_judgment": dict(judgment),
        "awaiting_goal_completion_human": False,
        "goal_completion_human": None,
        "goal_completion_resume": None,
        "mission_memory": recorded,
        "runtime_status_report": {
            "status": "COMPLETED" if judgment.get("status") == "judged" else "BLOCKED",
            "reason_code": persist_kwargs["stop_reason"],
        },
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-goal-completion-resume",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer),
            "final_llm_response_empty": not bool(answer.strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
    }


def _help_h_turn(
    user_text: str,
    session: dict[str, Any],
    *,
    model: str,
    correlation_id: str,
    memory: dict[str, Any],
) -> dict[str, Any]:
    """H2: /h slash command — Help only; never execute tools or start an agent loop."""
    help_result = help_handle_h(user_text)
    answer = format_help_for_chat(help_result)
    timestamp = now_iso()
    events = [
        event("request", text=user_text, route="help"),
        event("route", route="help", executor="help_system"),
        event(
            "help_h",
            ok=bool(help_result.get("ok")),
            operation=help_result.get("operation"),
            count=help_result.get("count"),
        ),
        event("final_answer", chars=len(answer or "")),
    ]
    return {
        "route": "help",
        "answer": answer,
        "events": events,
        "tool_used": False,
        "tools": [],
        "web_search": False,
        "research_saved": False,
        "executor": "help_system",
        "cursor_connected": False,
        "memory": memory,
        "task_runtime": None,
        "help_result": help_result,
        "final_llm_lifecycle": {
            "llm_request_id": f"{correlation_id}-help",
            "final_llm_request_started": False,
            "final_llm_request_started_at": None,
            "final_llm_response_received": True,
            "final_llm_response_received_at": timestamp,
            "final_llm_response_length": len(answer or ""),
            "final_llm_response_empty": not bool((answer or "").strip()),
            "final_response_accepted": True,
            "final_response_discarded": False,
            "late_response_received": False,
            "turn_closed_before_response": False,
            "empty_reason": None,
        },
        "model": model,
    }


def apply_development_policy_final_answer_boundary(result: dict[str, Any]) -> None:
    """P2a: single final-answer development policy enforce for run_chat_turn."""
    if "answer" not in result:
        return
    text = str(result.get("answer") or "")
    meta: dict[str, Any] = {"applied": False}
    try:
        from ai_tool.policy.enforce import apply_final_answer_policy, claims_specification_complete

        out = apply_final_answer_policy(text, items=None)
        result["answer"] = out.get("answer") or text
        meta["applied"] = bool(out.get("applied"))
        if out.get("notice"):
            meta["notice"] = out.get("notice")
    except Exception as exc:  # noqa: BLE001 窶・chat turn must continue
        meta["policy_application_error"] = f"{type(exc).__name__}: {exc}"
        claimed = False
        try:
            from ai_tool.policy.enforce import claims_specification_complete

            claimed = claims_specification_complete(text)
        except Exception:
            claimed = False
        if claimed:
            notice = (
                "[DEVELOPMENT_POLICY] completion_claim_verification_failed "
                "specification_status=NOT_OBSERVED "
                "may_claim_specification_complete=false "
                f"policy_application_error={type(exc).__name__}"
            )
            result["answer"] = text.rstrip() + "\n\n" + notice
            meta["applied"] = True
            meta["notice"] = notice
            meta["completion_claim_verification_failed"] = True
    result["policy_final_enforce"] = meta


def run_chat_turn(
    session: dict[str, Any],
    user_text: str,
    *,
    chat_fn: ChatFn | None = None,
    model: str | None = None,
    local_review_enabled: bool = False,
    review_chat_fn: ChatFn | None = None,
    handoff_packet: Mapping[str, Any] | None = None,
    pipeline_observer: PipelineObserver | None = None,
) -> dict[str, Any]:
    turn_started = time.perf_counter()
    timing = _new_timing_breakdown()
    text = str(user_text or "").strip()
    if not text:
        raise ValueError("message が空です")
    explicit_goal_command = text == "/goal" or text.startswith("/goal ")
    goal_usage_requested = text == "/goal"
    run_command_requested = text == "/run"
    if explicit_goal_command and not goal_usage_requested:
        text = text[len("/goal") :].strip()
    # H2: intercept /h before classify / agent turn (no tools, no LLM)
    if text.startswith("/h"):
        mdl = _resolve_runtime_model_name(model, session)
        session["model"] = mdl
        memory = _memory_overlay(text, session)
        case = attach_or_open_case(session, text)
        case_id = str(case.get("case_id") or "") or None
        sid = str(session.get("session_id") or "")
        correlation_id = new_correlation_id()
        begin_turn(sid, correlation_id, correlation_id)
        result = _help_h_turn(
            text,
            session,
            model=mdl,
            correlation_id=correlation_id,
            memory=memory,
        )
        timing["total_turn_ms"] = max(
            0, round((time.perf_counter() - turn_started) * 1000)
        )
        result["timing_breakdown"] = timing
        finish_turn(sid, correlation_id, cancelled=False, terminal_status=None)
        result["model"] = mdl
        result["session_id"] = session["session_id"]
        result["intent"] = "help"
        result["correlation_id"] = correlation_id
        result["case_id"] = case_id
        stamp_events(
            result.get("events") or [],
            correlation_id=correlation_id,
            model=mdl,
            session_id=str(session.get("session_id") or ""),
            case_id=case_id,
            requested_by="user",
        )
        result["development_job"] = None
        result["status_lines"] = public_status_lines(
            tool_used=False,
            tools=[],
            error=None,
            user_error=None,
            web_search=False,
            cursor_connected=False,
            model=mdl,
            research_saved=False,
        )
        result["pipeline"] = pipeline_steps(
            model=mdl,
            tools=[],
            error=None,
            user_error=None,
            web_search=False,
            search_available=True,
            research_saved=False,
        )
        result["session_summary"] = {
            "session_id": session.get("session_id"),
            "case_id": case_id,
            "turn_count": len(session.get("turns") or []) + 1,
            "model": mdl,
            "research": "NOT_CONNECTED",
            "memory": "未使用",
            "cursor_connected": False,
        }
        append_session_message(session, "user", text, model=mdl)
        apply_development_policy_final_answer_boundary(result)
        append_session_message(session, "assistant", str(result.get("answer") or ""), model=mdl)
        session["events"].extend(result.get("events") or [])
        session["turns"].append(
            {
                "user": text,
                "answer": result.get("answer"),
                "is_error": False,
                "user_error": None,
                "model": mdl,
                "route": "help",
                "tools": [],
                "events": result.get("events") or [],
                "pipeline": result.get("pipeline") or [],
                "web_search": False,
                "research_saved": False,
                "cursor_connected": False,
                "executor": "help_system",
                "memory": memory,
                "intent": "help",
                "correlation_id": correlation_id,
                "case_id": case_id,
                "requested_by": "user",
                "executed_by": "help_system",
                "help_result": result.get("help_result"),
            }
        )
        if case_id:
            record_turn(case_id, session["turns"][-1])
        session["research_saved"] = False
        save_session(session)
        return result

    fn = chat_fn or ollama_chat
    mdl = _resolve_runtime_model_name(model, session)
    session["model"] = mdl
    grill_state = None
    decision_change_packet = None
    boundary_grill_packet = None
    requirement_resolution_packet = None
    production_grill_packet = None
    if session.get("awaiting_decision_change_confirmation"):
        packet = session.get("decision_change_confirmation_state") or {}
        if (
            isinstance(packet, dict)
            and str(packet.get("mission_id") or "").strip()
            and isinstance(packet.get("pending_application"), dict)
        ):
            decision_change_packet = packet
    if session.get("awaiting_boundary_grill") and decision_change_packet is None:
        packet = session.get("boundary_grill_state") or {}
        if (
            isinstance(packet, dict)
            and str(packet.get("mission_id") or "").strip()
            and str(packet.get("original_request") or "").strip()
        ):
            boundary_grill_packet = packet
    if session.get("awaiting_human_grill"):
        packet = session.get("conversation_grill_state") or session.get("grill_resume")
        if isinstance(packet, dict) and str(packet.get("original_request") or "").strip():
            grill_state = packet
    if session.get("awaiting_requirement_resolution"):
        packet = session.get("requirement_resolution_state") or {}
        if (
            isinstance(packet, dict)
            and str(packet.get("mission_id") or "").strip()
            and str(packet.get("original_request") or "").strip()
        ):
            requirement_resolution_packet = packet
    if session.get("awaiting_production_grill_me"):
        packet = session.get("production_grill_me_state") or {}
        if (
            isinstance(packet, dict)
            and str(packet.get("mission_id") or "").strip()
            and str(packet.get("original_request") or "").strip()
        ):
            production_grill_packet = packet
    goal_completion_packet = None
    if session.get("awaiting_goal_completion_human"):
        packet = session.get("goal_completion_resume") or {}
        if (
            isinstance(packet, dict)
            and str(packet.get("mission_id") or "").strip()
            and str(packet.get("original_request") or "").strip()
        ):
            goal_completion_packet = packet
    production_handoff_requested = (
        grill_state is None
        and goal_completion_packet is None
        and boundary_grill_packet is None
        and decision_change_packet is None
        and is_explicit_production_handoff_trigger(text)
        and str(session.get("last_mission_id") or "").strip()
    )
    goal_continuation_packet = None
    goal_continuation_restore_errors: list[str] | None = None
    if (
        grill_state is None
        and goal_completion_packet is None
        and boundary_grill_packet is None
        and decision_change_packet is None
        and not production_handoff_requested
        and session.get("awaiting_goal_continuation")
        and is_explicit_continuation_trigger(text)
    ):
        packet = session.get("goal_continuation_resume") or {}
        restore_errors = validate_goal_continuation_packet(packet)
        if restore_errors:
            goal_continuation_restore_errors = restore_errors
        else:
            goal_continuation_packet = packet
    route = (
        "chat"
        if explicit_goal_command
        or run_command_requested
        or grill_state is not None
        or goal_completion_packet is not None
        or decision_change_packet is not None
        or boundary_grill_packet is not None
        or production_grill_packet is not None
        or requirement_resolution_packet is not None
        or goal_continuation_packet is not None
        or goal_continuation_restore_errors is not None
        else classify_request(text)
    )
    memory = _memory_overlay(text, session)
    case = attach_or_open_case(session, text)
    case_id = str(case.get("case_id") or "") or None
    job = maybe_record_job(session, text, route, case_id=case_id)
    sid = str(session.get("session_id") or "")
    jid = str((job or {}).get("id") or "") or None
    correlation_id = new_correlation_id()
    begin_turn(sid, correlation_id, correlation_id)
    orchestrator = None
    requirement = None
    requirement_resolution_early_result: dict[str, Any] | None = None
    phase3a_command_result = _phase3a_command_result(
        session=session,
        correlation_id=correlation_id,
        memory=memory,
        model=mdl,
        chat_fn=fn,
        goal_usage=goal_usage_requested,
        run_requested=run_command_requested,
    )
    goal_continuation_gate_blocked: dict[str, Any] | None = None
    concept_resolution = None
    grill_answer = None
    goal_continuation_context = None
    registry_tools = load_registry_tools() if route == "chat" else []
    available_tool_names = {
        str(item.get("name"))
        for item in registry_tools
        if item.get("visibility") == "agent" and item.get("name")
    }
    if phase3a_command_result is not None:
        pass
    elif grill_state is not None:
        grill_answer = text
        orchestrator = ChatTaskOrchestrator.restore_from_grill_resume(
            correlation_id,
            grill_state,
        )
        bind_execution_identity(
            orchestrator,
            resume_mission_id=str(grill_state.get("mission_id") or "") or None,
            new_execution=True,
        )
        restore_mission_clarifications(orchestrator)
        update_activity(
            sid,
            correlation_id,
            ActivityStatus.TASK_RUNNING,
            current_goal=orchestrator.runtime.goals[orchestrator.current_goal_id].title,
            current_task=orchestrator.task.title,
            task_status=orchestrator.task.status,
        )
    elif goal_completion_packet is not None:
        update_activity(sid, correlation_id, ActivityStatus.AWAITING_USER)
    elif goal_continuation_packet is not None:
        try:
            orchestrator = restore_orchestrator_from_goal_continuation(
                correlation_id,
                goal_continuation_packet,
            )
            mission_id = str(
                orchestrator.mission_id
                or goal_continuation_packet.get("mission_id")
                or ""
            ).strip()
            store = MissionMemoryStore.from_default()
            mission = store.get_mission(mission_id) if mission_id else None
            if mission is not None and mission_blocks_implementation_entry(mission):
                bundle = load_bundle_from_mission(mission)
                launched = launch_requirement_resolution_grill(
                    mission_id=mission_id,
                    original_request=str(mission.get("original_goal") or orchestrator.request),
                    bundle=bundle,
                )
                if launched is not None:
                    goal_continuation_gate_blocked = _requirement_resolution_blocked_turn(
                        correlation_id=correlation_id,
                        memory=memory,
                        model=mdl,
                        bundle=bundle,
                        mission_id=mission_id,
                        launched=launched,
                    )
                    goal_continuation_gate_blocked["events"] = [
                        event(
                            "goal_continuation_requirement_gate_blocked",
                            mission_id=mission_id,
                            phase=bundle.requirement_resolution_phase,
                        ),
                        *list(goal_continuation_gate_blocked.get("events") or []),
                    ]
                orchestrator = None
                goal_continuation_context = None
            else:
                capability_application = apply_continuation_winner(
                    orchestrator,
                    goal_continuation_packet,
                )
                goal_continuation_context = goal_continuation_context_from_packet(
                    goal_continuation_packet,
                    capability=capability_application,
                )
                orchestrator.configure_tool_expectation(
                    registry_tools,
                    registry_tools=registry_tools,
                )
                update_activity(
                    sid,
                    correlation_id,
                    ActivityStatus.TASK_RUNNING,
                    current_goal=orchestrator.runtime.goals[orchestrator.current_goal_id].title,
                    current_task=orchestrator.task.title,
                    task_status=orchestrator.task.status,
                )
        except GoalContinuationRestoreError as exc:
            goal_continuation_restore_errors = list(exc.errors or [exc.reason])
            orchestrator = None
            goal_continuation_context = None
    elif (
        not _blocks_new_goal_seed(
            requirement_resolution_packet=requirement_resolution_packet,
            production_grill_packet=production_grill_packet,
            goal_continuation_packet=goal_continuation_packet,
            goal_continuation_restore_errors=goal_continuation_restore_errors,
            production_handoff_requested=production_handoff_requested,
        )
        and route == "chat"
        and (
            explicit_goal_command
            or handoff_packet is not None
            or is_agent_task(
                text,
                known_tool_names=available_tool_names,
                agent_visible_tools=registry_tools,
            )
        )
    ):
        update_activity(sid, correlation_id, ActivityStatus.GOAL_CREATING)
        agent_task = explicit_goal_command or is_agent_task(
            text,
            known_tool_names=available_tool_names,
            agent_visible_tools=registry_tools,
        )
        concept_resolution = detect_unknown_concept(
            text, known_identifiers=available_tool_names
        )
        resolution_bundle: RequirementResolutionBundle | None = None
        requirement_resolution_blocked: dict[str, Any] | None = None
        semantic_revalidation_blocked: dict[str, Any] | None = None
        if handoff_packet is None:
            requirement = decompose_requirements(
                text,
                chat_fn=fn,
                model=mdl,
                available_tools=available_tool_names,
            )
            requirement = apply_concept_guidance_to_requirements(
                requirement, concept_resolution
            )
            if (
                requirement is not None
                and requirement.status != RequirementStatus.READY.value
            ):
                pass
            elif implementation_entry_requested(
                text,
                route=route,
                handoff_packet=handoff_packet,
                is_agent_task=agent_task,
            ):
                try:
                    resolution_chat = (
                        (lambda **kw: _timed_llm_call(fn, "requirement_resolution", timing, **kw))
                        if not _requirement_resolution_heuristic_enabled()
                        else fn
                    )
                    resolution_bundle = prepare_implementation_entry_bundle(
                        text,
                        chat_fn=resolution_chat,
                        model=mdl,
                        available_tools=available_tool_names,
                        handoff_packet=handoff_packet,
                        use_heuristic_only=_requirement_resolution_heuristic_enabled(),
                    )
                except Exception as exc:
                    requirement = RequirementDecomposition(
                        [],
                        RequirementStatus.MISSING_INPUT.value,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        source="requirement_resolution",
                    )
                    resolution_bundle = None
                if resolution_bundle is not None and requirements_block_implementation_entry(
                    resolution_bundle.requirement_resolution_phase,
                    resolution_bundle.structured_requirements,
                ):
                    mission_id = new_mission_id()
                    store = MissionMemoryStore.from_default()
                    store.put_mission(_new_mission_record(mission_id, resolution_bundle))
                    launched = launch_requirement_resolution_grill(
                        mission_id=mission_id,
                        original_request=text,
                        bundle=resolution_bundle,
                    )
                    if launched is not None:
                        requirement_resolution_blocked = _requirement_resolution_blocked_turn(
                            correlation_id=correlation_id,
                            memory=memory,
                            model=mdl,
                            bundle=resolution_bundle,
                            mission_id=mission_id,
                            launched=launched,
                        )
                if (
                    requirement_resolution_blocked is None
                    and resolution_bundle is not None
                    and should_run_semantic_revalidation_gate(
                        resolution_bundle=resolution_bundle
                    )
                ):
                    adopted_preview, constraints_preview = preview_implementation_adoption(
                        resolution_bundle,
                        [],
                    )
                    derived_spec = build_derived_spec_for_implementation_entry(
                        handoff_packet=handoff_packet,
                        completion_conditions=adopted_preview,
                        explicit_constraints=constraints_preview,
                    )
                    sem_result = run_implementation_semantic_revalidation(
                        resolution_bundle,
                        derived_spec,
                        resolved_context=resolved_context_from_handoff(handoff_packet),
                        chat_fn=fn,
                        model=mdl,
                        use_llm_open_compare=not _requirement_resolution_heuristic_enabled(),
                    )
                    if blocks_implementation_entry(sem_result):
                        mission_id = new_mission_id()
                        store = MissionMemoryStore.from_default()
                        store.put_mission(_new_mission_record(mission_id, resolution_bundle))
                        semantic_revalidation_blocked = _semantic_revalidation_blocked_turn(
                            correlation_id=correlation_id,
                            memory=memory,
                            model=mdl,
                            bundle=resolution_bundle,
                            mission_id=mission_id,
                            sem_result=sem_result,
                        )
        if requirement_resolution_blocked is not None:
            orchestrator = None
            requirement_resolution_early_result = requirement_resolution_blocked
        elif semantic_revalidation_blocked is not None:
            orchestrator = None
            requirement_resolution_early_result = semantic_revalidation_blocked
        elif handoff_packet is not None or (
            requirement is not None and requirement.status == RequirementStatus.READY.value
        ):
            adopted = (
                [item.description for item in requirement.conditions if item.required]
                if requirement is not None and requirement.source == "explicit"
                else []
            )
            if resolution_bundle is not None and resolution_bundle.structured_requirements:
                projected, constraints = project_to_runtime_adoption(
                    resolution_bundle.structured_requirements
                )
                if projected:
                    adopted = projected
            orchestrator = ChatTaskOrchestrator(
                correlation_id,
                text,
                completion_conditions=adopted,
                concept_resolution=concept_resolution,
            )
            orchestrator.user_explicit_conditions = list(adopted)
            if resolution_bundle is not None:
                _attach_requirement_contract(orchestrator, resolution_bundle)
                _, constraints = project_to_runtime_adoption(
                    resolution_bundle.structured_requirements
                )
                orchestrator.projected_explicit_constraints = list(constraints)
            orchestrator.initialize(handoff_packet=handoff_packet)
            bind_execution_identity(orchestrator, new_execution=True)
            if resolution_bundle is not None:
                store = MissionMemoryStore.from_default()
                mission_id = str(orchestrator.mission_id or new_mission_id())
                if not orchestrator.mission_id:
                    orchestrator.mission_id = mission_id
                store.put_mission(_new_mission_record(mission_id, resolution_bundle))
                if _should_start_production_grill_on_new_goal(
                    handoff_packet=handoff_packet,
                    text=text,
                    explicit_goal_command=explicit_goal_command,
                ):
                    phase1_step = run_production_grill_phase1(
                        orchestrator=orchestrator,
                        chat_fn=fn,
                        model=mdl,
                        store=store,
                    )
                    requirement_resolution_early_result = _production_grill_phase1_turn(
                        correlation_id=correlation_id,
                        memory=memory,
                        model=mdl,
                        mission_id=mission_id,
                        original_request=text,
                        step=phase1_step,
                        chat_fn=fn,
                    )
            update_activity(
                sid,
                correlation_id,
                ActivityStatus.TASK_RUNNING,
                current_goal=orchestrator.runtime.goals[orchestrator.current_goal_id].title,
                current_task=orchestrator.task.title,
                task_status=orchestrator.task.status,
            )

    if phase3a_command_result is not None:
        result = phase3a_command_result
    elif requirement is not None and requirement.status != RequirementStatus.READY.value:
        clarification = str(requirement.clarification or "完了条件を確認してください。")
        timestamp = now_iso()
        communication_failed = bool(requirement.error_type)
        error_text = str(requirement.error_message or "").casefold()
        failure_phase = (
            "requirement_resolution"
            if requirement.source == "requirement_resolution"
            else "requirement_decomposition"
        )
        result = {
            "route": "chat",
            "answer": clarification,
            "events": [event("requirement_validation", status=requirement.status)],
            "tool_used": False,
            "tools": [],
            "web_search": False,
            "research_saved": False,
            "executor": "local_agent",
            "cursor_connected": False,
            "memory": memory,
            "task_runtime": None,
            "requirement_decomposition": requirement.as_dict(),
            "concept_resolution": (
                concept_resolution.as_dict() if concept_resolution else None
            ),
            "execution_diagnostics": ({
                "communication_status": "FAILED",
                "failure_phase": failure_phase,
                "provider_reachable": "UNKNOWN",
                "provider_ready": "UNKNOWN",
                "model_available": False if "not found" in error_text else "UNKNOWN",
                "model_busy": "UNKNOWN",
                "exception_type": requirement.error_type,
                "exception_message": requirement.error_message,
            } if communication_failed else {}),
            "runtime_status_report": ({
                "status": "BLOCKED",
                "reason_code": "COMMUNICATION_FAILURE",
                "next_actions": ["LLM providerとmodel設定を確認して再実行"],
                "markdown": (
                    "処理を開始できませんでした。\n\n"
                    "理由: Requirement DecompositionのLLM通信に失敗しました。"
                ),
            } if communication_failed else {}),
            "final_llm_lifecycle": {
                "llm_request_id": f"{correlation_id}-clarification",
                "final_llm_request_started": True,
                "final_llm_request_started_at": timestamp,
                "final_llm_response_received": True,
                "final_llm_response_received_at": timestamp,
                "final_llm_response_length": len(clarification),
                "final_llm_response_empty": False,
                "final_response_accepted": True,
                "final_response_discarded": False,
                "late_response_received": False,
                "turn_closed_before_response": False,
                "empty_reason": None,
            },
        }
    elif goal_continuation_restore_errors is not None:
        result = _goal_continuation_restore_failed_turn(
            correlation_id=correlation_id,
            memory=memory,
            reason="invalid_packet",
            errors=goal_continuation_restore_errors,
        )
    elif production_handoff_requested:
        result = _production_handoff_turn(
            text,
            session,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
            chat_fn=fn,
        )
    elif goal_completion_packet is not None:
        result = _goal_completion_resume_turn(
            text,
            goal_completion_packet,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
        )
    elif decision_change_packet is not None:
        result = _decision_change_confirmation_resume_turn(
            text,
            decision_change_packet,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
            session=session,
            chat_fn=fn,
        )
    elif boundary_grill_packet is not None:
        result = _boundary_grill_resume_turn(
            text,
            boundary_grill_packet,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
            session=session,
            chat_fn=fn,
        )
    elif production_grill_packet is not None:
        result = _production_grill_resume_turn(
            text,
            production_grill_packet,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
            chat_fn=fn,
        )
    elif requirement_resolution_packet is not None:
        result = _requirement_resolution_resume_turn(
            text,
            requirement_resolution_packet,
            correlation_id=correlation_id,
            model=mdl,
            memory=memory,
            session=session,
            chat_fn=fn,
            timing=timing,
            local_review_enabled=local_review_enabled,
            review_chat_fn=review_chat_fn,
            pipeline_observer=pipeline_observer,
        )
    elif requirement_resolution_early_result is not None:
        result = requirement_resolution_early_result
    elif goal_continuation_gate_blocked is not None:
        result = goal_continuation_gate_blocked
    elif route == "tool_creation":
        result = _spec_proposal_turn(
            text,
            chat_fn=fn,
            model=mdl,
            source="chat_tool_creation",
            route="tool_creation",
            session_id=sid,
            development_job_id=jid,
            correlation_id=correlation_id,
            case_id=case_id,
        )
        result["memory"] = memory
    elif route == "development":
        result = _spec_proposal_turn(
            text,
            chat_fn=fn,
            model=mdl,
            source="chat_development",
            route="development",
            session_id=sid,
            development_job_id=jid,
            correlation_id=correlation_id,
            case_id=case_id,
        )
        result["memory"] = memory
    else:
        result = _chat_turn(
            text,
            session,
            chat_fn=fn,
            model=mdl,
            memory=memory,
            case_id=case_id,
            correlation_id=correlation_id,
            orchestrator=orchestrator,
            timing=timing,
            local_review_enabled=local_review_enabled,
            review_chat_fn=review_chat_fn,
            grill_answer=grill_answer,
            goal_continuation_context=goal_continuation_context,
            pipeline_observer=pipeline_observer,
        )
        if requirement is not None:
            result["requirement_decomposition"] = requirement.as_dict()
        if concept_resolution is not None:
            result["concept_resolution"] = concept_resolution.as_dict()

    apply_development_policy_final_answer_boundary(result)

    timing["total_turn_ms"] = max(
        0, round((time.perf_counter() - turn_started) * 1000)
    )
    result["timing_breakdown"] = timing
    if isinstance(result.get("task_runtime"), dict):
        result["task_runtime"]["timing"] = timing

    lifecycle = result.setdefault("final_llm_lifecycle", {})
    lifecycle["turn_finalization_started_at"] = now_iso()
    if not lifecycle.get("final_llm_response_received") and not result.get("cancelled"):
        lifecycle["turn_closed_before_response"] = True
        if not lifecycle.get("empty_reason"):
            lifecycle["empty_reason"] = "RESPONSE_NOT_RECEIVED"
    if result.get("cancelled") and not lifecycle.get("empty_reason"):
        lifecycle["empty_reason"] = "CANCELLED"
    report_status = str((result.get("runtime_status_report") or {}).get("status") or "")
    terminal_activity = {
        "IN_PROGRESS": ActivityStatus.BLOCKED,
        "AWAITING_USER": ActivityStatus.AWAITING_USER,
        "BLOCKED": ActivityStatus.BLOCKED,
        "FAILED": ActivityStatus.FAILED,
    }.get(report_status)
    finish_turn(
        sid,
        correlation_id,
        cancelled=bool(result.get("cancelled")),
        terminal_status=terminal_activity,
    )
    lifecycle["turn_finalization_finished_at"] = now_iso()

    result["model"] = mdl
    result["session_id"] = session["session_id"]
    result["intent"] = intent_of(route)
    result["correlation_id"] = correlation_id
    result["case_id"] = case_id
    stamp_events(
        result.get("events") or [],
        correlation_id=correlation_id,
        model=mdl,
        session_id=str(session.get("session_id") or ""),
        case_id=case_id,
        requested_by="user",
    )
    if job:
        job["proposal_id"] = (result.get("proposal") or {}).get("proposal_id")
        job["request_id"] = (result.get("proposal") or {}).get("request_id")
    result["development_job"] = job
    err = result.get("error") or result.get("spec_error")
    result["status_lines"] = public_status_lines(
        tool_used=bool(result.get("tool_used")),
        tools=result.get("tools") or [],
        error=err,
        user_error=result.get("user_error"),
        web_search=bool(result.get("web_search")),
        cursor_connected=False,
        model=mdl,
        research_saved=bool(result.get("research_saved")),
    )
    result["pipeline"] = pipeline_steps(
        model=mdl,
        tools=result.get("tools") or [],
        error=err,
        user_error=result.get("user_error"),
        web_search=bool(result.get("web_search")),
        search_available=True,
        research_saved=bool(result.get("research_saved")),
    )
    result["session_summary"] = {
        "session_id": session.get("session_id"),
        "case_id": case_id,
        "turn_count": len(session.get("turns") or []) + 1,
        "model": mdl,
        "research": "NOT_CONNECTED",
        "memory": "未使用",
        "cursor_connected": False,
    }
    append_session_message(session, "user", text, model=mdl)
    if job:
        append_session_message(
            session,
            "notice",
            (
                f"開発依頼として記録しました（Job {job['id']}）。"
                "Cursor には接続していません。成果物は開発タイムラインで確認できます。"
            ),
            model=mdl,
        )
    if result.get("is_error"):
        append_session_message(
            session,
            "error",
            str(result.get("user_error") or err or "エラー"),
            model=mdl,
        )
    else:
        append_session_message(session, "assistant", str(result.get("answer") or ""), model=mdl)
    session["events"].extend(result.get("events") or [])
    session["turns"].append(
        {
            "user": text,
            "answer": result.get("answer"),
            "is_error": bool(result.get("is_error")),
            "user_error": result.get("user_error"),
            "model": mdl,
            "route": result.get("route"),
            "tools": result.get("tools") or [],
            "events": result.get("events") or [],
            "pipeline": result.get("pipeline") or [],
            "web_search": result.get("web_search"),
            "research_saved": False,
            "cursor_connected": False,
            "executor": "local_agent",
            "memory": memory,
            "awaiting_human_review": result.get("awaiting_human_review"),
            "awaiting_human_grill": result.get("awaiting_human_grill"),
            "registry_write": result.get("registry_write"),
            "intent": result.get("intent"),
            "development_job_id": (job or {}).get("id") if job else None,
            "proposal_id": (result.get("proposal") or {}).get("proposal_id"),
            "request_id": (result.get("proposal") or {}).get("request_id"),
            "correlation_id": result.get("correlation_id"),
            "case_id": case_id,
            "requested_by": "user",
            "executed_by": "local_agent",
            "task_runtime": runtime_ui_summary(result.get("task_runtime")),
            "mission_memory": mission_ui_summary(result.get("mission_memory")),
            "goal_completion_judgment": result.get("goal_completion_judgment"),
            "awaiting_goal_completion_human": result.get("awaiting_goal_completion_human"),
            "answer_gate": result.get("answer_gate"),
        }
    )
    if case_id:
        record_turn(case_id, session["turns"][-1])
    session["research_saved"] = False
    session["last_test_result"] = session.get("last_test_result")
    if result.get("awaiting_human_review"):
        exp = session.get("experimental_session") or {}
        exp["awaiting_human_review"] = True
        session["experimental_session"] = exp
    if result.get("awaiting_human_grill"):
        session["awaiting_human_grill"] = True
        session["conversation_grill"] = result.get("conversation_grill")
        packet = None
        if isinstance(result.get("task_runtime"), dict):
            packet = result["task_runtime"].get("conversation_grill_state")
        session["conversation_grill_state"] = packet
    else:
        session["awaiting_human_grill"] = False
        session["conversation_grill"] = None
        session["conversation_grill_state"] = None
    if result.get("awaiting_goal_completion_human"):
        session["awaiting_goal_completion_human"] = True
        session["goal_completion_human"] = result.get("goal_completion_human")
        session["goal_completion_resume"] = result.get("goal_completion_resume")
    else:
        session["awaiting_goal_completion_human"] = False
        session["goal_completion_human"] = None
        session["goal_completion_resume"] = None
    if result.get("awaiting_decision_change_confirmation"):
        session["awaiting_decision_change_confirmation"] = True
        session["decision_change_confirmation_state"] = result.get(
            "decision_change_confirmation_state"
        )
        session["awaiting_boundary_grill"] = False
        session["boundary_grill"] = None
        session["boundary_grill_state"] = None
    else:
        session["awaiting_decision_change_confirmation"] = False
        session["decision_change_confirmation_state"] = None
    if result.get("awaiting_boundary_grill"):
        session["awaiting_boundary_grill"] = True
        session["boundary_grill"] = result.get("boundary_grill")
        session["boundary_grill_state"] = result.get("boundary_grill_state")
    else:
        session["awaiting_boundary_grill"] = False
        session["boundary_grill"] = None
        session["boundary_grill_state"] = None
    if result.get("awaiting_requirement_resolution"):
        session["awaiting_requirement_resolution"] = True
        session["requirement_resolution_grill"] = result.get("requirement_resolution_grill")
        session["requirement_resolution_state"] = result.get("requirement_resolution_state")
    else:
        session["awaiting_requirement_resolution"] = False
        session["requirement_resolution_grill"] = None
        session["requirement_resolution_state"] = None
    if result.get("awaiting_production_grill_me"):
        session["awaiting_production_grill_me"] = True
        session["production_grill_me"] = result.get("production_grill_me")
        session["production_grill_me_state"] = result.get("production_grill_me_state")
    else:
        session["awaiting_production_grill_me"] = False
        session["production_grill_me"] = None
        session["production_grill_me_state"] = None
        if result.get("aligned_spec"):
            session["production_aligned_spec"] = result.get("aligned_spec")
        if result.get("handoff_packet"):
            session["production_handoff_packet"] = result.get("handoff_packet")
            session["production_prd"] = result.get("prd")
            session["production_tech_spec"] = result.get("tech_spec")
            session["production_plan"] = result.get("plan")
            session["production_pipeline_status"] = result.get("production_status")
            if result.get("meaning_context"):
                session["production_meaning_context"] = result.get("meaning_context")
    if result.get("goal_continuation_restore_failed"):
        pass
    elif result.get("goal_continuation_resume"):
        new_packet = result.get("goal_continuation_resume") or {}
        prior_packet = session.get("goal_continuation_resume") or {}
        prior_mission = str(prior_packet.get("mission_id") or "")
        new_mission = str(new_packet.get("mission_id") or "")
        preserve_prior = (
            session.get("awaiting_goal_continuation")
            and prior_mission
            and new_mission
            and prior_mission != new_mission
            and not result.get("goal_continuation_restored")
        )
        if preserve_prior:
            pass
        else:
            session["awaiting_goal_continuation"] = True
            session["goal_continuation_resume"] = new_packet
    elif result.get("goal_continuation_restored") and not result.get(
        "goal_continuation_resume"
    ):
        session["awaiting_goal_continuation"] = False
        session["goal_continuation_resume"] = None
    elif result.get("awaiting_goal_continuation") is False:
        session["awaiting_goal_continuation"] = False
        session["goal_continuation_resume"] = None
    _sync_session_mission_pointer(session, result)
    save_session(session)
    return result
