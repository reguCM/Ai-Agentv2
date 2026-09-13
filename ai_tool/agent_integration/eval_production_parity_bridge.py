"""Eval Production Parity Bridge (CC-01) — canonical vs diagnostic eval paths.

Unifies evaluation so PASS/FAIL metrics use the same enforcement stack as Production
(gate → enrich → WebSessionTracker → boundary) without modifying Production code.

SCR-01 policy:
- Canonical (scored): production_mirror / this bridge — may drive STOP decisions.
- Diagnostic: execute_registry_tool direct — observation-only, never Production PASS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.agent_integration.production_agent_web_loop import (
    AgentWebLoopResult,
    ToolExecutionRecord,
    make_e2e_trust_file,
    run_production_agent_web_loop,
)
from ai_tool.agent_integration.trial import TrialExecutionRecord, TrialToolSelection, _mock_search_web

ChatFn = Callable[..., Any]
ToolFn = Callable[..., dict[str, Any]]

PATH_CANONICAL = "eval_parity_bridge"
PATH_DIAGNOSTIC_DIRECT = "eval_harness_direct"
PATH_PRODUCTION_MIRROR = "production_mirror"


@dataclass
class EvalPathMetadata:
    """Minimal path metadata aligned with existing Decision Log fields."""

    path_label: str
    backend: str | None
    production_equivalent: bool
    mock_or_live: str
    boundary_applied: bool
    web_session_tracker: bool
    diagnostic_only: bool
    scored: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def can_drive_production_decision(self) -> bool:
        """True only when metrics may influence STOP / Architecture decisions."""
        return self.production_equivalent and not self.diagnostic_only and self.scored


def infer_search_backend(result: dict[str, Any] | None) -> tuple[str | None, str]:
    """Return (backend, mock_or_live) from a search_web result dict."""
    if not isinstance(result, dict):
        return None, "unknown"
    hits = result.get("hits") or []
    if hits and isinstance(hits[0], dict):
        hit_backend = hits[0].get("backend")
        if hit_backend == "trial_mock":
            return "trial_mock", "mock"
        if hit_backend == "fixture":
            return "fixture", "fixture"
    backends = result.get("backends_tried") or []
    if backends:
        primary = str(backends[0])
        if primary == "trial_mock":
            return "trial_mock", "mock"
        if primary == "fixture":
            return "fixture", "fixture"
        return primary, "live"
    if result.get("fixture"):
        return "fixture", "fixture"
    if hits:
        return "live", "live"
    return None, "live"


def path_metadata_from_loop(
    loop: AgentWebLoopResult,
    *,
    scored: bool = True,
    search_backend: str | None = None,
    mock_or_live: str | None = None,
) -> EvalPathMetadata:
    search_exec = next((t for t in loop.tool_executions if t.tool_name == "search_web"), None)
    sr = (search_exec.result if search_exec else {}) or {}
    backend, mol = infer_search_backend(sr if isinstance(sr, dict) else None)
    if search_backend is not None:
        backend = search_backend
    if mock_or_live is not None:
        mol = mock_or_live
    label = loop.path or PATH_CANONICAL
    return EvalPathMetadata(
        path_label=label,
        backend=backend,
        production_equivalent=True,
        mock_or_live=mol,
        boundary_applied=bool(loop.boundary_applied),
        web_session_tracker=True,
        diagnostic_only=False,
        scored=scored,
    )


def path_metadata_from_direct(
    record: TrialExecutionRecord,
    *,
    tool_name: str,
    scored: bool = False,
) -> EvalPathMetadata:
    result = record.result if isinstance(record.result, dict) else {}
    backend, mol = infer_search_backend(result if tool_name == "search_web" else None)
    if tool_name != "search_web":
        backend = record.selection.source if record.selection else None
        mol = "mock" if backend == "trial_mock" else "live"
    return EvalPathMetadata(
        path_label=PATH_DIAGNOSTIC_DIRECT,
        backend=backend,
        production_equivalent=False,
        mock_or_live=mol,
        boundary_applied=False,
        web_session_tracker=False,
        diagnostic_only=True,
        scored=scored,
    )


def validate_stop_decision_integrity(
    *,
    decision: str,
    path_meta: EvalPathMetadata,
) -> dict[str, Any]:
    """Reject Production-level STOP when path is not production-equivalent."""
    production_decisions = {
        "STOP_NO_CHANGE",
        "STOP_A",
        "STOP_B",
        "STOP_C",
        "STOP_D",
        "STOP_E",
        "IMPLEMENT",
        "PRODUCTION_CANDIDATE",
    }
    requires_canonical = decision in production_decisions
    allowed = (not requires_canonical) or path_meta.can_drive_production_decision()
    return {
        "decision": decision,
        "path_label": path_meta.path_label,
        "production_equivalent": path_meta.production_equivalent,
        "diagnostic_only": path_meta.diagnostic_only,
        "allowed": allowed,
        "reason": (
            "canonical production-equivalent path"
            if allowed
            else "diagnostic/mock path cannot drive Production STOP decisions (SCR-01)"
        ),
    }


def loop_to_trial_executions(loop: AgentWebLoopResult) -> list[TrialExecutionRecord]:
    """Convert canonical loop executions to TrialExecutionRecord for legacy graders."""
    records: list[TrialExecutionRecord] = []
    for tex in loop.tool_executions:
        result = tex.result if isinstance(tex.result, dict) else {"raw": tex.result}
        ok = not tex.blocked
        if isinstance(result, dict):
            if result.get("ok") is False:
                ok = False
            elif result.get("blocked_by_agent_tool_gate"):
                ok = False
        records.append(
            TrialExecutionRecord(
                selection=TrialToolSelection(tex.tool_name, tex.arguments, PATH_CANONICAL, False),
                result=result,
                ok=ok,
                error=str(result.get("error") or "") if isinstance(result, dict) and result.get("error") else None,
            )
        )
    return records


def eval_path_fields(meta: EvalPathMetadata) -> dict[str, Any]:
    """Additive path metadata for harness result dicts."""
    return {
        "path_label": meta.path_label,
        "production_equivalent": meta.production_equivalent,
        "backend": meta.backend,
        "boundary_applied": meta.boundary_applied,
        "web_session_tracked": meta.web_session_tracker,
        "diagnostic_only": meta.diagnostic_only,
        "scored": meta.scored,
    }


def diagnostic_path_fields(*, backend: str | None = None) -> dict[str, Any]:
    """Standard diagnostic-only path metadata."""
    return {
        "path_label": PATH_DIAGNOSTIC_DIRECT,
        "production_equivalent": False,
        "backend": backend,
        "boundary_applied": False,
        "web_session_tracked": False,
        "diagnostic_only": True,
        "scored": False,
    }


def run_canonical_web_eval(
    user_request: str,
    *,
    chat_fn: ChatFn,
    model: str,
    search_web_fn: ToolFn | None = None,
    read_url_text_fn: ToolFn | None = None,
    trust_path: Path | None = None,
    max_rounds: int | None = None,
    live: bool = False,
    scored: bool = True,
    path_label: str = PATH_CANONICAL,
    system_prompt: str | None = None,
) -> tuple[AgentWebLoopResult, EvalPathMetadata]:
    """Canonical eval — same stack as Production mirror (gate, tracker, boundary)."""
    tp = trust_path
    if tp is None:
        tp = Path(".eval_trust") / "eval_parity_bridge_trust.json"
        make_e2e_trust_file(tp)

    loop = run_production_agent_web_loop(
        user_request,
        chat_fn=chat_fn,
        model=model,
        search_web_fn=search_web_fn,
        read_url_text_fn=read_url_text_fn,
        trust_path=tp,
        max_rounds=max_rounds,
        path_label=path_label,
        live=live,
        system_prompt=system_prompt,
    )
    meta = path_metadata_from_loop(loop, scored=scored)
    return loop, meta


def run_diagnostic_direct_eval(
    tool_name: str,
    arguments: Any,
    *,
    search_web_fn: ToolFn | None = None,
    scored: bool = False,
) -> tuple[TrialExecutionRecord, EvalPathMetadata]:
    """Diagnostic eval — execute_registry_tool direct; never production-equivalent."""
    record = execute_registry_tool(tool_name, arguments, search_web_fn=search_web_fn)
    meta = path_metadata_from_direct(record, tool_name=tool_name, scored=scored)
    return record, meta


def compare_path_divergence(
    *,
    query: str = "zzzz_nonexistent_xyz_12345",
) -> dict[str, Any]:
    """Demonstrate eval-direct mock default vs canonical empty-search fixture."""
    from ai_tool.agent_integration.trial import make_mock_chat_fn
    from ai_tool.agent_integration.trial_scenarios import TrialScenario

    def _empty_search(**_kw: Any) -> dict[str, Any]:
        return {"ok": True, "hits": [], "error": "検索結果がありません", "backends_tried": ["fixture"]}

    scenario = TrialScenario(
        scenario_id="parity_bridge_gap_probe",
        user_request="probe",
        expected_tool="search_web",
        routing_note="path divergence probe",
        mock_tool_calls=[{"name": "search_web", "arguments": {"query": query}}],
        mock_final_answer="275万人です。",
    )
    loop, canonical_meta = run_canonical_web_eval(
        "probe",
        chat_fn=make_mock_chat_fn(scenario),
        model="mock",
        search_web_fn=_empty_search,
        max_rounds=2,
        scored=True,
    )
    direct, diagnostic_meta = run_diagnostic_direct_eval(
        "search_web",
        {"query": query},
        search_web_fn=None,
    )
    direct_hits = len((direct.result or {}).get("hits") or [])
    return {
        "query": query,
        "canonical": {
            **canonical_meta.to_dict(),
            "hit_count": len(
                next(
                    (t.result.get("hits") or [] for t in loop.tool_executions if t.tool_name == "search_web"),
                    [],
                )
            ),
            "boundary_applied": loop.boundary_applied,
            "can_drive_production_decision": canonical_meta.can_drive_production_decision(),
        },
        "diagnostic": {
            **diagnostic_meta.to_dict(),
            "hit_count": direct_hits,
            "can_drive_production_decision": diagnostic_meta.can_drive_production_decision(),
        },
        "gap_confirmed": direct_hits > 0 and diagnostic_meta.backend == "trial_mock",
        "mock_pass_implies_production_pass": False,
    }


def defensive_core_policy() -> dict[str, Any]:
    """Model B — delegates to canonical Defensive Core Discovery Policy module."""
    from ai_tool.defensive_core_discovery_policy import policy_summary_for_harnesses

    return policy_summary_for_harnesses()


def assert_diagnostic_not_scored(meta: EvalPathMetadata) -> None:
    if meta.diagnostic_only and meta.scored:
        raise ValueError("diagnostic path must not be scored for Production metrics (SCR-01)")


__all__ = [
    "PATH_CANONICAL",
    "PATH_DIAGNOSTIC_DIRECT",
    "PATH_PRODUCTION_MIRROR",
    "EvalPathMetadata",
    "assert_diagnostic_not_scored",
    "compare_path_divergence",
    "defensive_core_policy",
    "diagnostic_path_fields",
    "eval_path_fields",
    "infer_search_backend",
    "loop_to_trial_executions",
    "path_metadata_from_direct",
    "path_metadata_from_loop",
    "run_canonical_web_eval",
    "run_diagnostic_direct_eval",
    "validate_stop_decision_integrity",
]
