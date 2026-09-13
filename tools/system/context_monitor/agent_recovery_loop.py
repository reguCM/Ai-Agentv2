"""Agent Loop への Recovery Evaluation 統合（P2-14）。P2-13 API を再利用。"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Callable

from tools.system.config import get_llm_profile
from tools.system.context_monitor.agent_recovery_bridge import (
    prepare_agent_recovery_evaluation,
    recovery_opt_in_enabled,
    submit_agent_recovery_selection,
)
from tools.system.context_monitor.agent_recovery_evaluation import (
    append_agent_recovery_evaluation,
    build_agent_evaluation_record,
)
from tools.system.context_monitor.failure_classifier import execution_needs_recovery
from tools.system.context_monitor.gpu_snapshot import snapshot_gpu
from tools.system.context_monitor.recovery import (
    RecoverySession,
    append_recovery_decision,
    build_execution_record,
    get_configured_context,
    is_automatic_recovery_enabled,
)


def agent_recovery_loop_enabled() -> bool:
    """AI_AGENT_RECOVERY_OPT_IN=1 で Agent Loop Recovery Evaluation を有効化。"""
    return recovery_opt_in_enabled()


def build_recovery_selection_prompt(brief: dict[str, Any]) -> str:
    """Agent へ Recovery Strategy 選択を求める構造化プロンプト。"""
    return (
        "以下の Recovery 状況を読み、最適な Recovery Strategy を1つ選んでください。\n"
        "Evidence Ranking は参考情報であり、必ず従う必要はありません。\n"
        "increase_context は最後の手段です（Gate 未成立時は実行されません）。\n\n"
        "=== Recovery Brief ===\n"
        f"{json.dumps(brief, ensure_ascii=False, indent=2)}\n\n"
        "=== 出力形式（JSON のみ。markdown 不可） ===\n"
        "{\n"
        '  "selected_strategy": "<strategy_name>",\n'
        '  "reason": "<選択理由>",\n'
        '  "confidence": "HIGH|MEDIUM|LOW|UNKNOWN",\n'
        '  "alternatives_considered": [\n'
        '    {"strategy": "<name>", "reason": "<理由>"}\n'
        "  ]\n"
        "}\n"
    )


def tool_result_is_execution_failure(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("blocked"):
        return False
    return result.get("ok") is False


def request_agent_recovery_selection(
    brief: dict[str, Any],
    *,
    chat_fn: Callable[..., Any] | None = None,
    model: str | None = None,
    selection_override: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Agent へ Selection を要求。override 指定時は LLM 呼び出しを省略（テスト用）。"""
    from tools.system.context_monitor.agent_recovery_evaluation import parse_agent_recovery_selection

    raw = selection_override
    if raw is None:
        if chat_fn is None:
            from tools.system.llm import chat as default_chat

            chat_fn = default_chat
        profile = get_llm_profile()
        use_model = model or str(profile.get("model") or "")
        prompt = build_recovery_selection_prompt(brief)
        response = chat_fn(
            model=use_model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = getattr(getattr(response, "message", None), "content", None) or ""

    try:
        selection = parse_agent_recovery_selection(raw)
        return {"ok": True, "selection": selection, "raw": raw}
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        return {
            "ok": False,
            "status": "selection_invalid",
            "error": str(exc),
            "raw": raw,
        }


def _build_execution_for_failure(
    *,
    response: Any | None = None,
    expected_tool: str | None = None,
    tool_execution_ok: bool | None = None,
    timeout: bool = False,
    error: str | None = None,
    task_type: str = "agent_loop",
    scenario_id: str | None = None,
    runtime_context: int | None = None,
) -> dict[str, Any]:
    profile = get_llm_profile()
    configured = get_configured_context(profile)
    runtime = runtime_context if runtime_context is not None else configured
    try:
        gpu_state = snapshot_gpu()
    except Exception:
        gpu_state = {"capture_error": True}

    thinking = ""
    if response is not None:
        try:
            thinking = str(response.message.model_dump().get("thinking") or "")
        except Exception:
            pass

    execution = build_execution_record(
        execution_id=str(uuid.uuid4()),
        model=str(profile.get("model") or ""),
        profile_id=profile.get("id"),
        configured_context=configured,
        runtime_context=runtime,
        task_type=task_type,
        scenario_id=scenario_id,
        response=response,
        expected_tool=expected_tool,
        tools_requested=True,
        tool_execution_ok=tool_execution_ok,
        timeout=timeout,
        error=error,
        gpu_state=gpu_state,
    )
    execution["thinking"] = thinking
    return execution


def _record_invalid_selection(
    *,
    execution: dict[str, Any],
    recommendation: dict[str, Any],
    selection_result: dict[str, Any],
    task_id: str | None = None,
    cycle_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation_id = str(uuid.uuid4())
    record = {
        **build_agent_evaluation_record(
            recommendation=recommendation,
            execution=execution,
            agent_selection={
                "selected_strategy": None,
                "reason": selection_result.get("error"),
                "confidence": "UNKNOWN",
            },
            cycle_state=cycle_state,
            evaluation_id=evaluation_id,
            task_id=task_id,
            approval_status="INVALID_SELECTION",
            execution_status="NOT_EXECUTED",
            selection_valid=False,
        ),
        "selection_valid": False,
        "selection_error": selection_result.get("error"),
        "agent_selection_raw": selection_result.get("raw"),
    }
    append_agent_recovery_evaluation(record)
    return record


def handle_agent_recovery_failure(
    *,
    response: Any | None = None,
    expected_tool: str | None = None,
    tool_execution_ok: bool | None = None,
    timeout: bool = False,
    error: str | None = None,
    task_type: str = "agent_loop",
    task_id: str | None = None,
    scenario_id: str | None = None,
    search_payload: dict[str, Any] | None = None,
    cycle_state: dict[str, Any] | None = None,
    chat_fn: Callable[..., Any] | None = None,
    model: str | None = None,
    selection_override: str | dict[str, Any] | None = None,
    session: RecoverySession | None = None,
) -> dict[str, Any] | None:
    """
    Failure → Ranking → Agent Brief → Agent Selection → Record → Approval 待ち。
    Recovery 自動実行なし。stop=True で Agent Loop 停止を指示。
    """
    if not agent_recovery_loop_enabled():
        return None

    execution = _build_execution_for_failure(
        response=response,
        expected_tool=expected_tool,
        tool_execution_ok=tool_execution_ok,
        timeout=timeout,
        error=error,
        task_type=task_type,
        scenario_id=scenario_id,
    )

    classification = execution.get("failure_classification") or {}
    if not execution_needs_recovery(classification):
        return None

    session = session or RecoverySession()
    prepared = prepare_agent_recovery_evaluation(
        execution,
        search_payload=search_payload,
        cycle_state=cycle_state,
        session=session,
    )
    recommendation = prepared["recommendation"]
    brief = prepared["agent_brief"]
    ranked = recommendation.get("normal_recommendations") or recommendation.get("recommendations") or []

    if not recommendation.get("recovery_required") or not ranked:
        record = build_agent_evaluation_record(
            recommendation=recommendation,
            execution=execution,
            agent_selection={
                "selected_strategy": None,
                "reason": "no recovery candidate",
                "confidence": "UNKNOWN",
            },
            cycle_state=cycle_state,
            task_id=task_id,
            approval_status="NO_CANDIDATE",
            execution_status="NOT_EXECUTED",
        )
        append_agent_recovery_evaluation(record)
        return {
            "stop": True,
            "status": "RECOVERY_REQUIRED_NO_CANDIDATE",
            "execution": execution,
            "recommendation": recommendation,
            "evaluation_id": record.get("evaluation_id"),
        }

    for decision in ranked:
        append_recovery_decision(decision)

    selection_result = request_agent_recovery_selection(
        brief,
        chat_fn=chat_fn,
        model=model,
        selection_override=selection_override,
    )

    if not selection_result.get("ok"):
        record = _record_invalid_selection(
            execution=execution,
            recommendation=recommendation,
            selection_result=selection_result,
            task_id=task_id,
            cycle_state=cycle_state,
        )
        return {
            "stop": True,
            "status": "SELECTION_INVALID",
            "execution": execution,
            "recommendation": recommendation,
            "evaluation_id": record.get("evaluation_id"),
            "error": selection_result.get("error"),
        }

    submitted = submit_agent_recovery_selection(
        execution,
        selection_result["selection"],
        recommendation=recommendation,
        cycle_state=cycle_state,
        human_approved=False,
        session=session,
        record=False,
    )

    evaluation = build_agent_evaluation_record(
        recommendation=recommendation,
        execution=execution,
        agent_selection=submitted["agent_selection"],
        cycle_state=cycle_state,
        task_id=task_id,
        approval_status="PENDING",
        execution_status=submitted["execution_plan"].get("execution_status"),
        execution_plan=submitted["execution_plan"],
        ranked_candidates=recommendation.get("recommendation_summary"),
        automatic_recovery_enabled=is_automatic_recovery_enabled(),
    )
    append_agent_recovery_evaluation(evaluation)

    return {
        "stop": True,
        "status": "AWAITING_HUMAN_APPROVAL",
        "execution": execution,
        "recommendation": recommendation,
        "agent_brief": brief,
        "agent_selection": submitted["agent_selection"],
        "ranking_vs_agent": submitted.get("ranking_vs_agent"),
        "execution_plan": submitted["execution_plan"],
        "evaluation_id": evaluation.get("evaluation_id"),
        "automatic_recovery_enabled": is_automatic_recovery_enabled(),
        "message": "Recovery Evaluation 完了。Human Approval 待ちで停止。",
    }


def print_agent_recovery_stop_notice(result: dict[str, Any]) -> None:
    """Agent Loop 停止時の CLI 通知。"""
    print("\n[AGENT_RECOVERY_EVALUATION]")
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "evaluation_id": result.get("evaluation_id"),
                "ranking_vs_agent": result.get("ranking_vs_agent"),
                "automatic_recovery_enabled": result.get("automatic_recovery_enabled"),
                "stop": result.get("stop"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if result.get("status") == "SELECTION_INVALID":
        print(f"Selection invalid: {result.get('error')}")
        return
    selection = result.get("agent_selection") or {}
    if selection:
        print(
            json.dumps(
                {
                    "agent_selected_strategy": selection.get("selected_strategy"),
                    "agent_confidence": selection.get("confidence"),
                    "agent_reason": selection.get("reason"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    plan = result.get("execution_plan") or {}
    if plan:
        print(f"Execution plan status: {plan.get('execution_status')}")
        if plan.get("blocked_by"):
            print(f"Blocked by: {plan.get('blocked_by')}")
    print("Human Approval 後にのみ Recovery 実行可能。自動 Recovery は OFF。")
