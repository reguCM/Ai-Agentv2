"""Recovery Harness: Live LLM で 16384 → Recovery → 32768 を検証。"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ai_tool.agent_integration.file_tools_integration_verify import file_tools_system_prompt
from ai_tool.agent_integration.gpu_process_e2e import (
    build_production_agent_tools,
    execute_registry_tool,
    ollama_tools_for_llm,
)
from ai_tool.agent_integration.trial import normalize_arguments
from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile
from tools.system.context_monitor.failure_classifier import execution_needs_recovery
from tools.system.context_monitor.gpu_snapshot import snapshot_gpu
from tools.system.context_monitor.paths import HARNESS_RUNS_DIR, ensure_monitor_dir
from tools.system.context_monitor.recovery import (
    RecoverySession,
    append_recovery_decision,
    append_recovery_result,
    build_execution_record,
    get_configured_context,
    propose_recovery,
)
from tools.system.context_monitor.recovery_helpers import (
    append_recovery_experience,
    evaluate_tool_call_recovery,
    format_recovery_approval_summary,
    tag_evidence_source,
)
from tools.system.llm import LLMTimeoutError, chat as ollama_chat

TASK_ID = "FILE-TOOLS-CONTEXT-RECOVERY-HARNESS-P2-11"
EVIDENCE_SOURCE_LIVE = "p2-11_live_recovery"
EVIDENCE_SOURCE_LEGACY = "legacy_observation"

_WIDE_USER = (
    "Tool Registryで read_file がどこで定義または参照されているか探して、"
    "重要なファイルを1つ選んで内容を確認してください。"
)
EXPECTED_TOOL = "read_file"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _thinking_from_response(response: Any) -> str:
    try:
        return str(response.message.model_dump().get("thinking") or "")
    except Exception:
        return ""


def build_fixed_payload_messages(search_payload: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    tools = build_production_agent_tools()
    tool_names = [t["function"]["name"] for t in tools]
    llm_tools = ollama_tools_for_llm(tools)
    payload = json.dumps(search_payload, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": file_tools_system_prompt(tool_names)},
        {"role": "user", "content": _WIDE_USER},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": {"path": ".", "query": "read_file"},
                    },
                }
            ],
        },
        {"role": "tool", "content": payload},
    ]
    meta = {
        "tool_schema": "production",
        "tool_names": tool_names,
        "llm_tools": llm_tools,
        "payload_bytes": len(payload.encode("utf-8")),
        "match_count": search_payload.get("match_count"),
        "truncated": search_payload.get("truncated"),
    }
    return messages, meta


def run_llm_attempt(
    messages: list[Any],
    llm_tools: list[Any],
    *,
    runtime_context: int,
    scenario_id: str,
    chat_fn: Callable[..., Any] | None = None,
    model: str | None = None,
    expected_tool: str = EXPECTED_TOOL,
) -> dict[str, Any]:
    """単一 LLM 呼び出し + GPU + execution 記録。"""
    profile = get_llm_profile()
    model = model or str(profile.get("model") or "")
    configured = get_configured_context(profile)
    chat = chat_fn or ollama_chat

    gpu_before = snapshot_gpu()
    started = time.perf_counter()
    response = None
    err: str | None = None
    timeout = False
    tool_execution_ok: bool | None = None

    try:
        response = chat(
            model=model,
            messages=messages,
            tools=llm_tools,
            runtime_context=runtime_context,
            context_monitor_meta={
                "task_type": "search_read",
                "scenario_id": scenario_id,
                "source": "recovery.harness",
            },
        )
    except LLMTimeoutError as exc:
        timeout = True
        err = str(exc)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
        timeout = "timeout" in err.lower()

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    gpu_after = snapshot_gpu()

    execution = build_execution_record(
        execution_id=str(uuid.uuid4()),
        model=model,
        profile_id=profile.get("id"),
        configured_context=configured,
        runtime_context=runtime_context,
        task_type="search_read",
        scenario_id=scenario_id,
        response=response,
        expected_tool=expected_tool,
        tool_execution_ok=tool_execution_ok,
        timeout=timeout,
        error=err,
        gpu_state=gpu_before,
        elapsed_ms=elapsed_ms,
    )
    if response is not None:
        execution["thinking"] = _thinking_from_response(response)

    if response is not None and execution.get("native_tool_call"):
        names = execution.get("native_tool_names") or []
        if expected_tool in names:
            for tc in getattr(response.message, "tool_calls", None) or []:
                if tc.function.name == expected_tool:
                    args = normalize_arguments(tc.function.arguments)
                    rec = execute_registry_tool(expected_tool, args)
                    tool_execution_ok = rec.ok
                    execution["tool_execution_ok"] = tool_execution_ok
                    execution["tool_execution_result"] = rec.result
                    break

    outcomes = evaluate_tool_call_recovery(
        native_tool_call=bool(execution.get("native_tool_call")),
        native_tool_names=execution.get("native_tool_names"),
        expected_tool=expected_tool,
        tool_execution_ok=execution.get("tool_execution_ok"),
        timeout=timeout,
        execution_result=execution.get("execution_result", "failure"),
    )
    execution.update(outcomes)

    return {
        "execution": execution,
        "response": response,
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "elapsed_ms": elapsed_ms,
        "timeout": timeout,
        "error": err,
    }


def _needs_recovery(execution: dict[str, Any], *, expected_tool: str) -> bool:
    names = execution.get("native_tool_names") or []
    if execution.get("tool_call_recovery") == "SUCCESS" and expected_tool in names:
        return False
    if execution_needs_recovery(execution.get("failure_classification", {})):
        return True
    if expected_tool not in names:
        return True
    if execution.get("tool_call_recovery") == "FAILURE":
        return True
    return False


def run_harness_attempt(
    *,
    scenario_id: str,
    search_payload: dict[str, Any] | None = None,
    primary_context: int | None = None,
    approve_recovery: bool = False,
    chat_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """1回: primary (16384) → 失敗時 Recovery 候補 → 承認時 32768 再試行。"""
    profile = get_llm_profile()
    configured = get_configured_context(profile)
    primary_ctx = primary_context if primary_context is not None else configured
    if search_payload is None:
        search_payload = search_files("read_file", path=".")

    messages, meta = build_fixed_payload_messages(search_payload)
    session = RecoverySession()

    primary = run_llm_attempt(
        messages,
        meta["llm_tools"],
        runtime_context=int(primary_ctx),
        scenario_id=f"{scenario_id}_primary",
        chat_fn=chat_fn,
    )
    primary_exec = primary["execution"]
    primary_needs_recovery = _needs_recovery(primary_exec, expected_tool=EXPECTED_TOOL)

    attempt_record: dict[str, Any] = {
        "scenario_id": scenario_id,
        "task_type": "search_read",
        "user_request": _WIDE_USER,
        "model": primary_exec.get("model"),
        "configured_context": configured,
        "initial_context": primary_ctx,
        "tool_schema": meta.get("tool_schema"),
        "search_payload": {
            "match_count": meta.get("match_count"),
            "payload_bytes": meta.get("payload_bytes"),
            "truncated": meta.get("truncated"),
        },
        "primary": {
            "context": primary_ctx,
            "execution_id": primary_exec.get("execution_id"),
            "execution_result": primary_exec.get("execution_result"),
            "tool_call_recovery": primary_exec.get("tool_call_recovery"),
            "task_result": primary_exec.get("task_result"),
            "failure_classification": primary_exec.get("failure_classification"),
            "native_tool_call": primary_exec.get("native_tool_call"),
            "native_tool_names": primary_exec.get("native_tool_names"),
            "tool_execution_ok": primary_exec.get("tool_execution_ok"),
            "timeout": primary.get("timeout"),
            "elapsed_ms": primary.get("elapsed_ms"),
            "gpu_before": primary.get("gpu_before"),
            "gpu_after": primary.get("gpu_after"),
        },
        "recovery": None,
        "recovery_outcome": "not_needed" if not primary_needs_recovery else "pending",
        "evidence_source_live": EVIDENCE_SOURCE_LIVE,
    }

    if not primary_needs_recovery:
        return attempt_record

    proposal = propose_recovery(primary_exec, session=session)
    decisions = proposal.get("decisions") or []
    if not decisions:
        attempt_record["recovery_outcome"] = "no_candidate"
        attempt_record["recovery_proposal"] = proposal
        return attempt_record

    decision = decisions[0]
    if decision.get("evidence"):
        decision["evidence"] = tag_evidence_source(
            {**decision["evidence"], "legacy_observations_used": True},
            EVIDENCE_SOURCE_LIVE,
        )
    decision["approval_summary"] = format_recovery_approval_summary(decision)
    attempt_record["recovery_proposal"] = proposal
    attempt_record["recovery_decision"] = decision

    if not approve_recovery:
        attempt_record["recovery_outcome"] = "approval_required"
        return attempt_record

    if not decision.get("execution_allowed"):
        attempt_record["recovery_outcome"] = "execution_blocked"
        return attempt_record

    append_recovery_decision(decision)
    retry = run_llm_attempt(
        messages,
        meta["llm_tools"],
        runtime_context=int(decision["candidate_context"]),
        scenario_id=f"{scenario_id}_recovery",
        chat_fn=chat_fn,
    )
    retry_exec = retry["execution"]
    session.record_attempt(context_used=int(decision["candidate_context"]))

    recovery_record = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parent_execution_id": primary_exec.get("execution_id"),
        "recovery_id": decision.get("recovery_id"),
        "attempt_number": decision.get("attempt_number"),
        "previous_context": decision.get("current_context"),
        "current_context": decision.get("candidate_context"),
        "configured_context": decision.get("configured_context"),
        "failure_type": decision.get("failure_type"),
        "candidate_strategy": decision.get("candidate_strategy"),
        "recovery_result": (
            "success" if retry_exec.get("tool_call_recovery") == "SUCCESS" else "failure"
        ),
        "execution_result": retry_exec.get("execution_result"),
        "retry_execution_id": retry_exec.get("execution_id"),
        "retry_execution": retry_exec,
        "tool_call_generated": retry_exec.get("native_tool_call"),
        "tool_execution_success": retry_exec.get("tool_execution_ok"),
        "latency_ms": retry.get("elapsed_ms"),
        "timeout": retry.get("timeout"),
        "gpu_before": retry.get("gpu_before"),
        "gpu_after": retry.get("gpu_after"),
        "evidence_source": EVIDENCE_SOURCE_LIVE,
    }
    append_recovery_result(recovery_record)

    retry_outcomes = {
        "tool_call_recovery": retry_exec.get("tool_call_recovery"),
        "task_result": retry_exec.get("task_result"),
        "execution_result": retry_exec.get("execution_result"),
    }

    attempt_record["recovery"] = {
        "recovery_id": decision.get("recovery_id"),
        "recovery_context": decision.get("candidate_context"),
        "recovery_result": recovery_record.get("recovery_result"),
        "execution_result": retry_outcomes.get("execution_result"),
        "tool_call_recovery": retry_outcomes.get("tool_call_recovery"),
        "task_result": retry_outcomes.get("task_result"),
        "tool_call_generated": retry_exec.get("native_tool_call"),
        "tool_execution_success": retry_exec.get("tool_execution_ok"),
        "timeout": retry.get("timeout"),
        "latency_ms": retry.get("elapsed_ms"),
        "gpu_before": retry.get("gpu_before"),
        "gpu_after": retry.get("gpu_after"),
        "retry_execution_id": retry_exec.get("execution_id"),
    }
    attempt_record["recovery_outcome"] = recovery_record.get("recovery_result", "unknown")

    append_recovery_experience(
        {
            "experience_id": str(uuid.uuid4()),
            "task_id": TASK_ID,
            "evidence_source": EVIDENCE_SOURCE_LIVE,
            "model": primary_exec.get("model"),
            "hardware": (primary.get("gpu_before") or {}).get("gpu_name"),
            "task_type": "search_read",
            "scenario_id": scenario_id,
            "failure_type": decision.get("failure_type"),
            "initial_context": primary_ctx,
            "candidate_context": decision.get("candidate_context"),
            "recovery_strategy": decision.get("candidate_strategy"),
            "gpu_condition": {
                "before_primary": primary.get("gpu_before"),
                "after_primary": primary.get("gpu_after"),
                "before_recovery": retry.get("gpu_before"),
                "after_recovery": retry.get("gpu_after"),
            },
            "primary_tool_call_recovery": primary_exec.get("tool_call_recovery"),
            "recovery_tool_call_recovery": retry_exec.get("tool_call_recovery"),
            "result": recovery_record.get("recovery_result"),
            "validation": "provisional",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    return attempt_record


def run_harness_batch(
    *,
    runs: int = 3,
    approve_recovery: bool = False,
    chat_fn: Callable[..., Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """複数回 Live Harness 実行。"""
    ensure_monitor_dir()
    profile = get_llm_profile()
    ts = _utc_stamp()
    out_dir = output_dir or (HARNESS_RUNS_DIR / f"{ts}_recovery_harness_p211")
    out_dir.mkdir(parents=True, exist_ok=True)

    search_payload = search_files("read_file", path=".")
    attempts: list[dict[str, Any]] = []
    for i in range(1, runs + 1):
        print(f"[P2-11 harness] run {i}/{runs}...", flush=True)
        attempts.append(
            run_harness_attempt(
                scenario_id=f"p211_fixed_payload_{i}",
                search_payload=search_payload,
                approve_recovery=approve_recovery,
                chat_fn=chat_fn,
            )
        )

    summary = _summarize_batch(attempts)
    report = {
        "task_id": TASK_ID,
        "timestamp": ts,
        "model": profile.get("model"),
        "configured_context": get_configured_context(profile),
        "automatic_recovery_enabled": False,
        "evidence_source_live": EVIDENCE_SOURCE_LIVE,
        "scenario": "fixed_50match_payload_post_search",
        "runs_requested": runs,
        "runs_completed": len(attempts),
        "attempts": attempts,
        "summary": summary,
    }
    out_path = out_dir / "harness.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["output_path"] = str(out_path)
    return report


def _summarize_batch(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    primary_ok = sum(
        1
        for a in attempts
        if (a.get("primary") or {}).get("tool_call_recovery") == "SUCCESS"
    )
    primary_fail = sum(
        1
        for a in attempts
        if (a.get("primary") or {}).get("tool_call_recovery") == "FAILURE"
    )
    recovery_ran = [a for a in attempts if a.get("recovery")]
    recovery_success = sum(
        1
        for a in recovery_ran
        if (a.get("recovery") or {}).get("tool_call_recovery") == "SUCCESS"
    )
    failure_to_success = sum(
        1
        for a in attempts
        if (a.get("primary") or {}).get("tool_call_recovery") == "FAILURE"
        and (a.get("recovery") or {}).get("tool_call_recovery") == "SUCCESS"
    )
    return {
        "primary_success_count": primary_ok,
        "primary_failure_count": primary_fail,
        "recovery_attempted_count": len(recovery_ran),
        "recovery_tool_call_success_count": recovery_success,
        "failure_to_recovery_success_count": failure_to_success,
        "live_16384_to_32768_confirmed": failure_to_success > 0,
    }
