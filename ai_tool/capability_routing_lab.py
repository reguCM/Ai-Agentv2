"""Capability Routing Lab v0 — Hard capability gap demonstration (non-production).

Proves pre-execution routing for tool_calling without a production Auto Router.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from tools.system.llm_tool_capability import probe_tool_calling
from tools.system.model_registry import get_model, is_tool_calling_supported

EXECUTION_PROFILE_TOOL = "fast_tool"

ECHO_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "echo_probe",
        "description": "Echo the input string back",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
}


@dataclass(frozen=True)
class LabWorker:
    worker_id: str
    provider_model: str
    registry_capabilities: dict[str, Any]
    effective_capabilities: list[str]
    eligible: bool
    ineligible_reason: str | None = None


@dataclass(frozen=True)
class LabTask:
    case_id: str
    description: str
    required_capabilities: list[str]
    expected_tool: str
    prompt: str


@dataclass
class CapabilityRoutingObservation:
    case_id: str
    arm: str
    required_capabilities: list[str]
    candidate_worker_id: str
    provider_model: str
    effective_capabilities: list[str]
    eligible: bool
    routing_reason: str | None
    selected_worker_id: str | None
    execution_profile: str
    success: bool
    failure_reason: str | None
    native_tool_call: bool
    tool_names: list[str]
    tool_arguments: list[Any]
    latency_ms: float
    content_preview: str = ""
    skipped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _effective_capabilities_for_worker(
    worker_id: str,
    *,
    live_probe: Mapping[str, Any] | None = None,
) -> list[str]:
    caps: list[str] = ["text"]
    registry_row = get_model(worker_id)
    registry_caps = dict(registry_row.get("capabilities") or {})
    if is_tool_calling_supported(worker_id):
        caps.append("tool_calling")
    elif live_probe and live_probe.get("supported") is True:
        caps.append("tool_calling")
    if registry_caps.get("coding", {}).get("supported"):
        caps.append("coding")
    return sorted(dict.fromkeys(caps))


def build_workers(
    worker_ids: Sequence[str],
    *,
    required_capabilities: Sequence[str],
    probe_fn: Callable[[str], Mapping[str, Any]] | None = None,
) -> list[LabWorker]:
    probe = probe_fn or probe_tool_calling
    rows: list[LabWorker] = []
    required = set(required_capabilities)
    for worker_id in worker_ids:
        registry_row = get_model(worker_id)
        provider_model = str(registry_row.get("model") or worker_id)
        live = probe(provider_model)
        effective = _effective_capabilities_for_worker(worker_id, live_probe=live)
        missing = sorted(required - set(effective))
        if "tool_calling" in required and live.get("supported") is False:
            eligible = False
            reason = f"live_probe_tool_calling_unsupported: {live.get('error')}"
        elif missing:
            eligible = False
            reason = f"missing_capabilities: {missing}"
        else:
            eligible = True
            reason = None
        rows.append(
            LabWorker(
                worker_id=worker_id,
                provider_model=provider_model,
                registry_capabilities=dict(registry_row.get("capabilities") or {}),
                effective_capabilities=effective,
                eligible=eligible,
                ineligible_reason=reason,
            )
        )
    return rows


def default_tool_task() -> LabTask:
    return LabTask(
        case_id="hard-gap-tool-calling-echo",
        description="Native Ollama tool_call required to invoke echo_probe",
        required_capabilities=["tool_calling"],
        expected_tool="echo_probe",
        prompt="Call echo_probe with text exactly: ROUTING_LAB_OK",
    )


def _execute_tool_task(
    worker: LabWorker,
    task: LabTask,
    *,
    chat_fn: Callable[..., Any],
    arm: str,
    routing_reason: str | None,
    selected_worker_id: str | None,
    skipped: bool = False,
) -> CapabilityRoutingObservation:
    if skipped:
        return CapabilityRoutingObservation(
            case_id=task.case_id,
            arm=arm,
            required_capabilities=list(task.required_capabilities),
            candidate_worker_id=worker.worker_id,
            provider_model=worker.provider_model,
            effective_capabilities=list(worker.effective_capabilities),
            eligible=worker.eligible,
            routing_reason=routing_reason,
            selected_worker_id=selected_worker_id,
            execution_profile=EXECUTION_PROFILE_TOOL,
            success=False,
            failure_reason=worker.ineligible_reason,
            native_tool_call=False,
            tool_names=[],
            tool_arguments=[],
            latency_ms=0.0,
            skipped=True,
        )

    started = time.perf_counter()
    try:
        response = chat_fn(
            model=worker.provider_model,
            messages=[{"role": "user", "content": task.prompt}],
            tools=[ECHO_PROBE_TOOL],
            execution_profile=EXECUTION_PROFILE_TOOL,
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        return CapabilityRoutingObservation(
            case_id=task.case_id,
            arm=arm,
            required_capabilities=list(task.required_capabilities),
            candidate_worker_id=worker.worker_id,
            provider_model=worker.provider_model,
            effective_capabilities=list(worker.effective_capabilities),
            eligible=worker.eligible,
            routing_reason=routing_reason,
            selected_worker_id=selected_worker_id,
            execution_profile=EXECUTION_PROFILE_TOOL,
            success=False,
            failure_reason=str(exc),
            native_tool_call=False,
            tool_names=[],
            tool_arguments=[],
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    message = getattr(response, "message", None)
    tool_calls = getattr(message, "tool_calls", None) or []
    names: list[str] = []
    args: list[Any] = []
    for call in tool_calls:
        fn = getattr(call, "function", None)
        if fn is None:
            continue
        name = str(getattr(fn, "name", "") or "")
        if name:
            names.append(name)
        args.append(getattr(fn, "arguments", None))
    success = task.expected_tool in names
    return CapabilityRoutingObservation(
        case_id=task.case_id,
        arm=arm,
        required_capabilities=list(task.required_capabilities),
        candidate_worker_id=worker.worker_id,
        provider_model=worker.provider_model,
        effective_capabilities=list(worker.effective_capabilities),
        eligible=worker.eligible,
        routing_reason=routing_reason,
        selected_worker_id=selected_worker_id,
        execution_profile=EXECUTION_PROFILE_TOOL,
        success=success,
        failure_reason=error,
        native_tool_call=bool(names),
        tool_names=names,
        tool_arguments=args,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        content_preview=str(getattr(message, "content", "") or "")[:120],
    )


def run_arm_a_direct(
    workers: Sequence[LabWorker],
    task: LabTask,
    *,
    primary_worker_id: str,
    chat_fn: Callable[..., Any],
) -> list[CapabilityRoutingObservation]:
    worker = next(row for row in workers if row.worker_id == primary_worker_id)
    return [
        _execute_tool_task(
            worker,
            task,
            chat_fn=chat_fn,
            arm="A",
            routing_reason="direct_execution_without_capability_gate",
            selected_worker_id=worker.worker_id,
        )
    ]


def run_arm_b_routed(
    workers: Sequence[LabWorker],
    task: LabTask,
    *,
    chat_fn: Callable[..., Any],
) -> list[CapabilityRoutingObservation]:
    observations: list[CapabilityRoutingObservation] = []
    selected: LabWorker | None = None
    for worker in workers:
        if not worker.eligible:
            observations.append(
                _execute_tool_task(
                    worker,
                    task,
                    chat_fn=chat_fn,
                    arm="B",
                    routing_reason="ineligible_skipped_before_execution",
                    selected_worker_id=None,
                    skipped=True,
                )
            )
            continue
        if selected is None:
            selected = worker
            observations.append(
                _execute_tool_task(
                    worker,
                    task,
                    chat_fn=chat_fn,
                    arm="B",
                    routing_reason="first_eligible_worker_selected",
                    selected_worker_id=worker.worker_id,
                )
            )
        else:
            observations.append(
                _execute_tool_task(
                    worker,
                    task,
                    chat_fn=chat_fn,
                    arm="B",
                    routing_reason="eligible_but_not_selected",
                    selected_worker_id=selected.worker_id,
                    skipped=True,
                )
            )
    return observations


def summarize_routing_lab(observations: Sequence[CapabilityRoutingObservation]) -> dict[str, Any]:
    by_arm: dict[str, list[CapabilityRoutingObservation]] = {"A": [], "B": []}
    for row in observations:
        by_arm.setdefault(row.arm, []).append(row)

    def _executed(rows: Sequence[CapabilityRoutingObservation]) -> CapabilityRoutingObservation | None:
        executed_rows = [row for row in rows if not row.skipped]
        return executed_rows[0] if executed_rows else None

    arm_a = _executed(by_arm.get("A", []))
    arm_b = _executed(by_arm.get("B", []))
    return {
        "arm_a_success": bool(arm_a and arm_a.success),
        "arm_b_success": bool(arm_b and arm_b.success),
        "arm_a_failure_reason": arm_a.failure_reason if arm_a else None,
        "arm_b_selected_worker": arm_b.selected_worker_id if arm_b else None,
        "arm_b_skipped_workers": [
            row.candidate_worker_id
            for row in by_arm.get("B", [])
            if row.skipped and not row.eligible
        ],
        "routing_demonstrated": bool(arm_a and not arm_a.success and arm_b and arm_b.success),
    }


def write_observations_jsonl(
    observations: Sequence[CapabilityRoutingObservation],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in observations:
            handle.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
    return path


def run_capability_routing_lab(
    *,
    output_dir: Path,
    worker_ids: Sequence[str] = ("deepseek_coder_v2_16b", "qwen3_14b"),
    primary_worker_id: str = "deepseek_coder_v2_16b",
    chat_fn: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if chat_fn is None:
        from tools.system.llm import chat as default_chat

        chat_fn = default_chat

    task = default_tool_task()
    workers = build_workers(worker_ids, required_capabilities=task.required_capabilities)
    observations = run_arm_a_direct(
        workers,
        task,
        primary_worker_id=primary_worker_id,
        chat_fn=chat_fn,
    )
    observations.extend(run_arm_b_routed(workers, task, chat_fn=chat_fn))
    summary = summarize_routing_lab(observations)
    stamp = _utc_stamp()
    jsonl_path = write_observations_jsonl(
        observations,
        output_dir / f"capability_routing_lab_{stamp}.jsonl",
    )
    payload = {
        "task": asdict(task),
        "workers": [asdict(worker) for worker in workers],
        "summary": summary,
        "observations_jsonl": str(jsonl_path),
    }
    summary_path = output_dir / f"capability_routing_lab_{stamp}_summary.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["summary_json"] = str(summary_path)
    return payload


__all__ = [
    "CapabilityRoutingObservation",
    "LabTask",
    "LabWorker",
    "build_workers",
    "default_tool_task",
    "run_arm_a_direct",
    "run_arm_b_routed",
    "run_capability_routing_lab",
    "summarize_routing_lab",
]
