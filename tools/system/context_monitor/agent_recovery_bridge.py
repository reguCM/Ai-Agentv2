"""Agent Loop から Recovery Engine への opt-in 接続（自動実行なし）。"""
from __future__ import annotations

import json
import os
from typing import Any

from tools.system.config import get_llm_profile
from tools.system.context_monitor.agent_recovery_evaluation import (
    append_agent_recovery_evaluation,
    build_agent_evaluation_record,
    build_agent_recovery_brief,
    enrich_recommendation_with_strategy_evidence,
    parse_agent_recovery_selection,
    record_agent_recovery_outcome,
    resolve_agent_selection_for_execution,
)
from tools.system.context_monitor.failure_classifier import execution_needs_recovery
from tools.system.context_monitor.gpu_snapshot import snapshot_gpu
from tools.system.context_monitor.recovery import (
    RecoverySession,
    append_recovery_decision,
    build_execution_record,
    get_configured_context,
    is_automatic_recovery_enabled,
    recommend_recovery_strategies,
)
from tools.system.context_monitor.recovery_helpers import (
    format_recovery_approval_summary,
    format_recommendation_list,
)


def recovery_opt_in_enabled() -> bool:
    """AI_AGENT_RECOVERY_OPT_IN=1 で Agent が Recovery 候補まで生成。"""
    return os.environ.get("AI_AGENT_RECOVERY_OPT_IN", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def prepare_agent_recovery_evaluation(
    execution: dict[str, Any],
    *,
    search_payload: dict[str, Any] | None = None,
    cycle_state: dict[str, Any] | None = None,
    session: RecoverySession | None = None,
) -> dict[str, Any]:
    """Evidence Ranking + Agent 評価用ブリーフを生成（実行なし）。"""
    recommendation = recommend_recovery_strategies(
        execution,
        search_payload=search_payload,
        session=session,
        cycle_state=cycle_state,
    )
    recommendation = enrich_recommendation_with_strategy_evidence(recommendation)
    brief = build_agent_recovery_brief(recommendation, execution, cycle_state=cycle_state)
    return {
        "recommendation": recommendation,
        "agent_brief": brief,
        "automatic_recovery_enabled": is_automatic_recovery_enabled(),
    }


def submit_agent_recovery_selection(
    execution: dict[str, Any],
    agent_response: str | dict[str, Any],
    *,
    recommendation: dict[str, Any],
    cycle_state: dict[str, Any] | None = None,
    human_approved: bool = False,
    session: RecoverySession | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """
    Agent の構造化選択を受け取り、Ranking 比較を記録。
    実行は human_approved 後のみ resolve 可能。
    """
    agent_selection = parse_agent_recovery_selection(agent_response)
    evaluation = build_agent_evaluation_record(
        recommendation=recommendation,
        execution=execution,
        agent_selection=agent_selection,
        cycle_state=cycle_state,
    )
    if record:
        append_agent_recovery_evaluation(evaluation)

    execution_plan = resolve_agent_selection_for_execution(
        agent_selection,
        recommendation,
        execution,
        cycle_state=cycle_state,
        human_approved=human_approved,
        session=session,
    )

    return {
        "evaluation": evaluation,
        "agent_selection": agent_selection,
        "execution_plan": execution_plan,
        "ranking_vs_agent": evaluation.get("ranking_vs_agent"),
        "automatic_recovery_enabled": is_automatic_recovery_enabled(),
    }


def evaluate_llm_round_for_recovery(
    response: Any,
    *,
    expected_tool: str | None = None,
    task_type: str = "unknown",
    scenario_id: str | None = None,
    runtime_context: int | None = None,
    tools_requested: bool = True,
    timeout: bool = False,
    error: str | None = None,
    cycle_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Opt-in 時: Tool Calling 失敗を検出し Recovery 候補を返す。
    自動 retry は行わない。APPROVAL_REQUIRED で停止情報を返す。
    """
    if not recovery_opt_in_enabled():
        return None
    if is_automatic_recovery_enabled():
        pass

    profile = get_llm_profile()
    configured = get_configured_context(profile)
    runtime = runtime_context if runtime_context is not None else configured

    try:
        gpu_state = snapshot_gpu()
    except Exception:
        gpu_state = {"capture_error": True}

    thinking = ""
    try:
        thinking = str(response.message.model_dump().get("thinking") or "") if response else ""
    except Exception:
        pass

    execution = build_execution_record(
        model=str(profile.get("model") or ""),
        profile_id=profile.get("id"),
        configured_context=configured,
        runtime_context=runtime,
        task_type=task_type,
        scenario_id=scenario_id,
        response=response,
        expected_tool=expected_tool,
        tools_requested=tools_requested,
        timeout=timeout,
        error=error,
        gpu_state=gpu_state,
    )
    execution["thinking"] = thinking

    if not execution_needs_recovery(execution.get("failure_classification", {})):
        return None

    prepared = prepare_agent_recovery_evaluation(
        execution,
        cycle_state=cycle_state,
    )
    recommendation = prepared["recommendation"]
    ranked = recommendation.get("normal_recommendations") or recommendation.get("recommendations") or []
    if not recommendation.get("recovery_required") or not ranked:
        return {
            "status": "RECOVERY_REQUIRED_NO_CANDIDATE",
            "execution": execution,
            "recommendation": recommendation,
            "agent_brief": prepared.get("agent_brief"),
        }

    for decision in ranked:
        append_recovery_decision(decision)

    top = ranked[0]
    ctx_exp = recommendation.get("context_expansion") or {}
    return {
        "status": "AGENT_EVALUATION_REQUIRED",
        "automatic_recovery_enabled": is_automatic_recovery_enabled(),
        "execution": execution,
        "recommendation": recommendation,
        "agent_brief": prepared.get("agent_brief"),
        "situation": recommendation.get("situation"),
        "recommendation_summary": recommendation.get("recommendation_summary"),
        "context_expansion": ctx_exp,
        "top_candidate": top,
        "approval_summary": format_recovery_approval_summary(top),
        "recommendation_list": format_recommendation_list(recommendation),
        "message": "Recovery 候補を生成しました。Agent 評価後、明示承認が必要です。",
    }


def print_recovery_opt_in_notice(result: dict[str, Any]) -> None:
    print("\n[RECOVERY_OPT_IN]")
    print(json.dumps({"status": result.get("status")}, ensure_ascii=False))
    if result.get("recommendation_list"):
        print(result["recommendation_list"])
    elif result.get("approval_summary"):
        print(result["approval_summary"])
    ctx = result.get("context_expansion") or {}
    if ctx:
        print(
            f"Context Expansion (increase_context): gate={ctx.get('gate_status')} "
            f"(last-resort, separate from normal ranking)"
        )
