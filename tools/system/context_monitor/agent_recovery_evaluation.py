"""Agent Recovery 候補評価・選択の観測（P2-13）。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from tools.system.context_monitor.context_expansion_gate import evaluate_context_expansion_gate
from tools.system.context_monitor.paths import AGENT_RECOVERY_EVALUATIONS_JSONL, ensure_monitor_dir
from tools.system.context_monitor.recovery_evidence import summarize_strategy_evidence
from tools.system.context_monitor.schema import (
    AGENT_EVALUATION_SCHEMA_VERSION,
    CONFIDENCE_LEVELS,
    RANKING_VS_AGENT,
    RECOVERY_STRATEGIES,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_strategy(name: str) -> str:
    if name == "explicit_tool_instruction":
        return "retry_with_explicit_tool_instruction"
    return name


def build_agent_recovery_brief(
    recommendation: dict[str, Any],
    execution: dict[str, Any],
    *,
    cycle_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Agent へ渡す構造化 Recovery 評価ブリーフ。"""
    situation = recommendation.get("situation") or {}
    classification = execution.get("failure_classification") or recommendation.get("failure_classification") or {}
    normal = recommendation.get("normal_recommendations") or recommendation.get("recommendations") or []
    ctx_exp = recommendation.get("context_expansion") or {}
    evidence_summary = recommendation.get("evidence_summary") or {}

    strategy_evidence: list[dict[str, Any]] = []
    for row in normal:
        strat = row.get("candidate_strategy") or ""
        hist = row.get("historical_summary") or evidence_summary.get(strat) or {}
        strategy_evidence.append(
            {
                "strategy": strat,
                "rank": row.get("strategy_rank"),
                "rank_score": row.get("rank_score"),
                "confidence": row.get("confidence"),
                "evidence_count": row.get("evidence_count"),
                "positive_evidence_count": hist.get("positive_evidence_count"),
                "negative_evidence_count": hist.get("negative_evidence_count"),
                "tool_call_success_rate": hist.get("tool_call_success_rate"),
                "avg_latency_ms": hist.get("avg_latency_ms"),
                "recommendation_reasons": row.get("recommendation_reasons") or [],
                "execution_allowed": row.get("execution_allowed"),
            }
        )

    cycle = cycle_state or {}
    return {
        "schema_version": AGENT_EVALUATION_SCHEMA_VERSION,
        "current_situation": {
            "failure_type": situation.get("failure_type") or classification.get("failure_type"),
            "failure_reason": classification.get("failure_type"),
            "task_type": execution.get("task_type"),
            "expected_tool": execution.get("expected_tool"),
            "tool_result_count": situation.get("tool_result_count"),
            "payload_bytes": situation.get("payload_bytes"),
            "truncated": situation.get("truncated"),
            "configured_context": situation.get("configured_context") or execution.get("configured_context"),
            "runtime_context": situation.get("runtime_context") or execution.get("runtime_context"),
            "gpu_vram_free_mib": situation.get("vram_free_mib"),
            "recovery_cycle": {
                "tried_strategies": cycle.get("tried_strategies") or [],
                "context_expansion_used": cycle.get("context_expansion_used", False),
                "normal_recovery_attempted": cycle.get("normal_recovery_attempted", False),
                "task_unresolved": cycle.get("task_unresolved", False),
            },
        },
        "evidence_ranking": [
            {
                "rank": r.get("strategy_rank"),
                "strategy": r.get("candidate_strategy"),
                "rank_score": r.get("rank_score"),
                "confidence": r.get("confidence"),
                "evidence_count": r.get("evidence_count"),
            }
            for r in normal
        ],
        "strategy_evidence": strategy_evidence,
        "context_expansion": {
            "strategy": "increase_context",
            "gate_status": ctx_exp.get("gate_status", "BLOCKED"),
            "blocked_reasons": ctx_exp.get("blocked_reasons") or [],
            "candidate_context": ctx_exp.get("candidate_context"),
            "note": "最後の手段。通常候補と同列ではない。Gate 条件成立 + Human Approval が必要。",
        },
        "response_schema": {
            "selected_strategy": "string (required)",
            "reason": "string (required)",
            "confidence": "HIGH|MEDIUM|LOW|UNKNOWN (required)",
            "alternatives_considered": [
                {"strategy": "string", "reason": "string"},
            ],
        },
    }


def parse_agent_recovery_selection(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Agent 出力を構造化パース。自由文章のみは拒否。"""
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
    else:
        data = dict(raw)

    selected = _normalize_strategy(str(data.get("selected_strategy") or "").strip())
    reason = str(data.get("reason") or "").strip()
    confidence = str(data.get("confidence") or "UNKNOWN").upper()

    if not selected:
        raise ValueError("selected_strategy is required")
    if selected not in RECOVERY_STRATEGIES:
        raise ValueError(f"unknown strategy: {selected}")
    if not reason:
        raise ValueError("reason is required")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "UNKNOWN"

    alternatives: list[dict[str, str]] = []
    for alt in data.get("alternatives_considered") or []:
        if not isinstance(alt, dict):
            continue
        strat = _normalize_strategy(str(alt.get("strategy") or "").strip())
        alt_reason = str(alt.get("reason") or "").strip()
        if strat:
            alternatives.append({"strategy": strat, "reason": alt_reason})

    return {
        "selected_strategy": selected,
        "reason": reason,
        "confidence": confidence,
        "alternatives_considered": alternatives,
    }


def compare_ranking_vs_agent(
    ranking_top_strategy: str | None,
    agent_selected_strategy: str | None,
) -> str:
    if not ranking_top_strategy:
        return "NO_RANKING"
    if not agent_selected_strategy:
        return "NO_RANKING"
    top = _normalize_strategy(ranking_top_strategy)
    selected = _normalize_strategy(agent_selected_strategy)
    return "MATCH" if top == selected else "DIFFERENT"


def ranking_top_strategy(recommendation: dict[str, Any]) -> str | None:
    normal = recommendation.get("normal_recommendations") or recommendation.get("recommendations") or []
    if not normal:
        return None
    return normal[0].get("candidate_strategy")


def build_agent_evaluation_record(
    *,
    recommendation: dict[str, Any],
    execution: dict[str, Any],
    agent_selection: dict[str, Any],
    cycle_state: dict[str, Any] | None = None,
    evaluation_id: str | None = None,
    task_id: str | None = None,
    approval_status: str | None = None,
    execution_status: str | None = None,
    execution_plan: dict[str, Any] | None = None,
    ranked_candidates: list[dict[str, Any]] | None = None,
    automatic_recovery_enabled: bool | None = None,
    selection_valid: bool = True,
) -> dict[str, Any]:
    top = ranking_top_strategy(recommendation)
    selected = agent_selection.get("selected_strategy")
    comparison = compare_ranking_vs_agent(top, selected)
    classification = execution.get("failure_classification") or {}
    record = {
        "schema_version": AGENT_EVALUATION_SCHEMA_VERSION,
        "record_type": "evaluation",
        "evaluation_id": evaluation_id or str(uuid.uuid4()),
        "timestamp": _utc_now_iso(),
        "task_id": task_id or execution.get("scenario_id"),
        "parent_execution_id": execution.get("execution_id"),
        "scenario_id": execution.get("scenario_id"),
        "failure_type": classification.get("failure_type"),
        "situation": recommendation.get("situation"),
        "ranked_candidates": ranked_candidates or recommendation.get("recommendation_summary"),
        "ranking_top_strategy": top,
        "agent_selected_strategy": selected,
        "agent_selection": agent_selection,
        "ranking_vs_agent": comparison,
        "agent_reason": agent_selection.get("reason"),
        "agent_confidence": agent_selection.get("confidence"),
        "alternatives_considered": agent_selection.get("alternatives_considered") or [],
        "evidence_ranking": recommendation.get("recommendation_summary"),
        "context_expansion_gate": (recommendation.get("context_expansion") or {}).get("gate_status"),
        "approval_status": approval_status or "PENDING",
        "execution_status": execution_status or "NOT_EXECUTED",
        "execution_plan": execution_plan,
        "selection_valid": selection_valid,
        "automatic_recovery_enabled": automatic_recovery_enabled,
        "cycle_state": cycle_state,
        "note": "Agent judgment is observed, not final Recovery Engine decision",
    }
    return record


def append_agent_recovery_evaluation(record: dict[str, Any], *, path=None) -> str:
    ensure_monitor_dir()
    target = path or AGENT_RECOVERY_EVALUATIONS_JSONL
    eid = record.get("evaluation_id") or str(uuid.uuid4())
    record["evaluation_id"] = eid
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return eid


def load_agent_recovery_evaluations(*, path=None) -> list[dict[str, Any]]:
    target = path or AGENT_RECOVERY_EVALUATIONS_JSONL
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def resolve_agent_selection_for_execution(
    agent_selection: dict[str, Any],
    recommendation: dict[str, Any],
    execution: dict[str, Any],
    *,
    cycle_state: dict[str, Any] | None = None,
    human_approved: bool = False,
    session=None,
) -> dict[str, Any]:
    """
    Agent 選択を実行計画へ変換。increase_context は Gate 必須。
    自動実行しない。
    """
    selected = agent_selection.get("selected_strategy")
    normal = recommendation.get("normal_recommendations") or recommendation.get("recommendations") or []
    ctx_exp = recommendation.get("context_expansion") or {}

    if selected == "increase_context":
        gate = evaluate_context_expansion_gate(
            execution=execution,
            cycle_state=cycle_state,
            context_expansion_decision=ctx_exp.get("decision"),
            normal_recommendations=normal,
            session=session,
            human_approved=human_approved,
            check_approval=True,
        )
        if gate.get("gate_status") != "ALLOWED":
            return {
                "execution_status": "BLOCKED",
                "blocked_by": "context_expansion_gate",
                "gate": gate,
                "agent_selection": agent_selection,
                "note": "Agent selected increase_context but gate conditions not met",
            }
        decision = ctx_exp.get("decision") or {}
        return {
            "execution_status": "APPROVAL_READY",
            "selected_strategy": selected,
            "decision": decision,
            "gate": gate,
            "agent_selection": agent_selection,
            "requires_human_approval": True,
        }

    decision = next((d for d in normal if d.get("candidate_strategy") == selected), None)
    if decision is None:
        return {
            "execution_status": "BLOCKED",
            "blocked_by": "strategy_not_in_normal_candidates",
            "agent_selection": agent_selection,
        }

    if not human_approved:
        return {
            "execution_status": "APPROVAL_REQUIRED",
            "selected_strategy": selected,
            "decision": decision,
            "agent_selection": agent_selection,
            "requires_human_approval": True,
        }

    if not decision.get("execution_allowed"):
        return {
            "execution_status": "BLOCKED",
            "blocked_by": "execution_not_allowed",
            "decision": decision,
            "agent_selection": agent_selection,
        }

    return {
        "execution_status": "APPROVAL_READY",
        "selected_strategy": selected,
        "decision": decision,
        "agent_selection": agent_selection,
        "requires_human_approval": False,
    }


def record_agent_recovery_outcome(
    *,
    evaluation_id: str,
    agent_selection: dict[str, Any],
    recovery_execution: dict[str, Any] | None = None,
    task_result: str | None = None,
    path=None,
) -> dict[str, Any]:
    """
    Agent 選択 / Recovery 実行 / Task 結果を分離して記録。
    agent_selection ≠ recovery success ≠ task success
    """
    recovery_exec = recovery_execution or {}
    record = {
        "schema_version": AGENT_EVALUATION_SCHEMA_VERSION,
        "record_type": "outcome",
        "evaluation_id": evaluation_id,
        "timestamp": _utc_now_iso(),
        "agent_selection": {
            "selected_strategy": agent_selection.get("selected_strategy"),
            "reason": agent_selection.get("reason"),
            "confidence": agent_selection.get("confidence"),
        },
        "recovery_execution": {
            "executed": recovery_exec.get("executed", False),
            "recovery_result": recovery_exec.get("recovery_result"),
            "tool_call_recovery": recovery_exec.get("tool_call_recovery"),
            "timeout": recovery_exec.get("timeout"),
            "latency_ms": recovery_exec.get("latency_ms"),
        },
        "task_result": task_result,
        "note": "agent_selection, recovery_execution, task_result are separate",
    }
    append_agent_recovery_evaluation(record, path=path)
    return record


def enrich_recommendation_with_strategy_evidence(
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    """Evidence サマリを recommendation に付与（Agent 提示用）。"""
    summary = recommendation.get("evidence_summary")
    if summary is None:
        summary = summarize_strategy_evidence()
        recommendation = {**recommendation, "evidence_summary": summary}
    return recommendation
