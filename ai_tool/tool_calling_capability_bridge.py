"""Hard capability bridge v0 — tool_calling only (non-production Auto Router).

Resolves whether the current Local Worker can enter an Agent LLM call with
non-empty ``tools=`` before Ollama rejects the request.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, Mapping, Sequence

from tools.system.llm_tool_capability import probe_tool_calling
from tools.system.model_registry import (
    ModelNotFoundError,
    get_model,
    list_models,
    resolve_provider_model_name,
    tool_calling_capability,
)

HARD_CAPABILITY_TOOL_CALLING = "tool_calling"

EligibilityState = Literal["eligible", "ineligible", "indeterminate"]

# Explicit fallback priority — not registry enumeration order.
TOOL_CALLING_FALLBACK_CANDIDATES: tuple[str, ...] = (
    "qwen3_8b",
    "qwen3_14b",
    "qwen2_5_coder_7b",
)


@dataclass(frozen=True)
class ToolCallingBridgeResult:
    required_capabilities: list[str]
    current_model: str
    current_worker_id: str | None
    current_model_eligible: bool
    selected_model: str
    selected_worker_id: str | None
    routing_performed: bool
    routing_reason: str | None
    capability_source: str
    capability_gap: bool
    gap_reason: str | None
    execution_profile: str | None = None
    bridge_applied: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_registry_worker_id(identifier: str | None) -> str | None:
    """Map profile id / registry id / provider model name to registry model id."""
    token = str(identifier or "").strip()
    if not token:
        return None
    resolved = resolve_provider_model_name(token)
    for item in list_models():
        identities = {
            str(item.get("id") or "").strip(),
            str(item.get("profile_id") or "").strip(),
            str(item.get("model") or "").strip(),
        }
        if token in identities or resolved in identities:
            return str(item.get("id") or "").strip() or None
    return None


def derive_required_hard_capabilities(llm_tools: Sequence[Any] | None) -> list[str]:
    if llm_tools:
        return [HARD_CAPABILITY_TOOL_CALLING]
    return []


def _probe_eligibility_state(result: Mapping[str, Any]) -> EligibilityState:
    if result.get("supported") is True:
        return "eligible"
    if result.get("supported") is False:
        detail = str(result.get("detail") or "")
        error = str(result.get("error") or "").casefold()
        if detail == "ollama_rejected_tools_parameter" or "does not support tools" in error:
            return "ineligible"
    return "indeterminate"


def worker_tool_calling_eligibility(
    worker_id: str,
    *,
    probe_fn: Callable[[str], Mapping[str, Any]] | None = None,
) -> tuple[EligibilityState, str, str | None]:
    """Return (state, capability_source, reason)."""
    try:
        row = get_model(worker_id)
    except ModelNotFoundError:
        return "indeterminate", "unknown", f"model_not_in_registry:{worker_id}"

    provider_model = str(row.get("model") or worker_id)
    tc = tool_calling_capability(worker_id)
    if tc.get("verified"):
        if bool(tc.get("supported")):
            return "eligible", "registry_verified", None
        return "ineligible", "registry_verified", "registry_tool_calling_unsupported"

    probe = probe_fn or probe_tool_calling
    result = probe(provider_model)
    state = _probe_eligibility_state(result)
    if state == "eligible":
        return "eligible", "live_probe", None
    if state == "ineligible":
        return "ineligible", "live_probe", str(result.get("error") or "tool_calling_probe_failed")
    return "indeterminate", "unknown", str(result.get("error") or "tool_calling_probe_indeterminate")


def _ordered_candidates(
    current_worker_id: str | None,
    fallback_candidates: Sequence[str],
) -> list[str]:
    ordered: list[str] = []
    if current_worker_id:
        ordered.append(current_worker_id)
    for worker_id in fallback_candidates:
        token = str(worker_id or "").strip()
        if token and token not in ordered:
            ordered.append(token)
    return ordered


def apply_tool_calling_hard_capability_bridge(
    current_model: str,
    *,
    llm_tools: Sequence[Any] | None,
    fallback_candidates: Sequence[str] | None = None,
    probe_fn: Callable[[str], Mapping[str, Any]] | None = None,
    execution_profile: str | None = None,
) -> ToolCallingBridgeResult:
    """Select execution model for Agent Loop tool-calling entry."""
    provider_model = resolve_provider_model_name(current_model)
    required = derive_required_hard_capabilities(llm_tools)
    if not required:
        worker_id = resolve_registry_worker_id(provider_model)
        return ToolCallingBridgeResult(
            required_capabilities=[],
            current_model=provider_model,
            current_worker_id=worker_id,
            current_model_eligible=True,
            selected_model=provider_model,
            selected_worker_id=worker_id,
            routing_performed=False,
            routing_reason="llm_tools_empty",
            capability_source="not_applicable",
            capability_gap=False,
            gap_reason=None,
            execution_profile=execution_profile,
            bridge_applied=False,
        )

    candidates = tuple(fallback_candidates or TOOL_CALLING_FALLBACK_CANDIDATES)
    current_worker_id = resolve_registry_worker_id(provider_model)
    current_state: EligibilityState = "indeterminate"
    current_source = "unknown"
    current_reason: str | None = None

    if current_worker_id:
        current_state, current_source, current_reason = worker_tool_calling_eligibility(
            current_worker_id,
            probe_fn=probe_fn,
        )
    else:
        probe = probe_fn or probe_tool_calling
        probe_result = probe(provider_model)
        current_state = _probe_eligibility_state(probe_result)
        current_source = "live_probe" if current_state != "indeterminate" else "unknown"
        current_reason = (
            None
            if current_state == "eligible"
            else str(probe_result.get("error") or "unregistered_model_probe_indeterminate")
        )

    if current_state == "eligible":
        return ToolCallingBridgeResult(
            required_capabilities=required,
            current_model=provider_model,
            current_worker_id=current_worker_id,
            current_model_eligible=True,
            selected_model=provider_model,
            selected_worker_id=current_worker_id,
            routing_performed=False,
            routing_reason="current_worker_eligible",
            capability_source=current_source,
            capability_gap=False,
            gap_reason=None,
            execution_profile=execution_profile,
        )

    if current_state == "indeterminate":
        return ToolCallingBridgeResult(
            required_capabilities=required,
            current_model=provider_model,
            current_worker_id=current_worker_id,
            current_model_eligible=False,
            selected_model=provider_model,
            selected_worker_id=current_worker_id,
            routing_performed=False,
            routing_reason="current_worker_indeterminate",
            capability_source=current_source,
            capability_gap=True,
            gap_reason=current_reason or "tool_calling_eligibility_indeterminate",
            execution_profile=execution_profile,
        )

    for worker_id in _ordered_candidates(current_worker_id, candidates):
        if worker_id == current_worker_id:
            continue
        state, source, _reason = worker_tool_calling_eligibility(
            worker_id,
            probe_fn=probe_fn,
        )
        if state != "eligible":
            continue
        selected_model = str(get_model(worker_id).get("model") or worker_id)
        return ToolCallingBridgeResult(
            required_capabilities=required,
            current_model=provider_model,
            current_worker_id=current_worker_id,
            current_model_eligible=False,
            selected_model=selected_model,
            selected_worker_id=worker_id,
            routing_performed=True,
            routing_reason=(
                f"current_worker_ineligible:{current_reason or 'tool_calling_unsupported'};"
                f"selected_fallback:{worker_id}"
            ),
            capability_source=source,
            capability_gap=False,
            gap_reason=None,
            execution_profile=execution_profile,
        )

    return ToolCallingBridgeResult(
        required_capabilities=required,
        current_model=provider_model,
        current_worker_id=current_worker_id,
        current_model_eligible=False,
        selected_model=provider_model,
        selected_worker_id=current_worker_id,
        routing_performed=False,
        routing_reason="no_eligible_local_worker",
        capability_source=current_source,
        capability_gap=True,
        gap_reason=current_reason or "no_eligible_local_worker_for_tool_calling",
        execution_profile=execution_profile,
    )


__all__ = [
    "HARD_CAPABILITY_TOOL_CALLING",
    "TOOL_CALLING_FALLBACK_CANDIDATES",
    "ToolCallingBridgeResult",
    "apply_tool_calling_hard_capability_bridge",
    "derive_required_hard_capabilities",
    "resolve_registry_worker_id",
    "worker_tool_calling_eligibility",
]
