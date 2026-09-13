"""Context Recovery Strategy エンジン（本番自動発動 OFF）。"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from tools.system.config import get_llm_profile
from tools.system.context_monitor.failure_classifier import (
    classify_execution_record,
    classify_llm_response,
    execution_needs_recovery,
)
from tools.system.context_monitor.gpu_snapshot import snapshot_gpu
from tools.system.context_monitor.paths import (
    RECOVERY_DECISIONS_JSONL,
    RECOVERY_POLICY_JSON,
    RECOVERY_RESULTS_JSONL,
    ensure_monitor_dir,
)
from tools.system.context_monitor.record import append_observation, build_observation, load_observations
from tools.system.context_monitor.schema import CONFIDENCE_LEVELS, RECOVERY_STRATEGIES


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_recovery_policy(path=None) -> dict[str, Any]:
    with open(path or RECOVERY_POLICY_JSON, encoding="utf-8") as f:
        return json.load(f)


def is_automatic_recovery_enabled(policy: dict[str, Any] | None = None) -> bool:
    """本番自動 Recovery。デフォルト OFF。環境変数でも上書き可。"""
    env = os.environ.get("AI_AGENT_AUTOMATIC_RECOVERY", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    policy = policy or load_recovery_policy()
    return bool(policy.get("automatic_recovery_enabled", False))


def get_configured_context(profile: dict[str, Any] | None = None) -> int | None:
    profile = profile or get_llm_profile()
    ctx = profile.get("context_limit")
    return int(ctx) if ctx is not None else None


def get_model_context_limit(model: str, profile_id: str | None, policy: dict[str, Any] | None = None) -> int | None:
    policy = policy or load_recovery_policy()
    limits = policy.get("model_context_limits") or {}
    for key in (model, profile_id):
        if key and key in limits:
            return int(limits[key])
    return None


def get_pc_context_limit(policy: dict[str, Any] | None = None) -> int | None:
    policy = policy or load_recovery_policy()
    val = policy.get("pc_context_limit")
    return int(val) if val is not None else None


def next_context_step(current: int, policy: dict[str, Any] | None = None) -> int | None:
    """Context ladder で一段階上げる。"""
    policy = policy or load_recovery_policy()
    ladder = sorted(int(x) for x in (policy.get("context_ladder") or []))
    for ctx in ladder:
        if ctx > current:
            return ctx
    return None


def validate_candidate_context(
    candidate: int,
    *,
    current: int,
    model: str,
    profile_id: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Model/PC 上限チェック。"""
    policy = policy or load_recovery_policy()
    model_limit = get_model_context_limit(model, profile_id, policy)
    pc_limit = get_pc_context_limit(policy)
    reasons: list[str] = []
    valid = True
    if candidate <= current:
        valid = False
        reasons.append("candidate must exceed current context")
    if model_limit is not None and candidate > model_limit:
        valid = False
        reasons.append(f"candidate {candidate} exceeds model_limit {model_limit}")
    if pc_limit is not None and candidate > pc_limit:
        valid = False
        reasons.append(f"candidate {candidate} exceeds pc_limit {pc_limit}")
    return {
        "valid": valid,
        "candidate_context": candidate,
        "model_context_limit": model_limit,
        "pc_context_limit": pc_limit,
        "reasons": reasons,
    }


def gpu_observation_allows_execution(
    gpu_state: dict[str, Any] | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GPU 観測情報。固定 VRAM 閾値は使わない。"""
    policy = policy or load_recovery_policy()
    gpu_cfg = policy.get("gpu_safety") or {}
    if not gpu_cfg.get("require_observation_for_execution", True):
        return {"execution_allowed": True, "block_reason": None}

    if not gpu_state or gpu_state.get("capture_error"):
        if gpu_cfg.get("block_if_status_unavailable", True):
            return {
                "execution_allowed": False,
                "block_reason": "gpu_observation_unavailable",
            }

    status = (gpu_state or {}).get("gpu_status") or gpu_state or {}
    total = (gpu_state or {}).get("vram_total_mib") or status.get("vram_total")
    if total is None and gpu_cfg.get("block_if_vram_total_unknown", True):
        return {
            "execution_allowed": False,
            "block_reason": "vram_total_unknown",
        }

    return {
        "execution_allowed": True,
        "block_reason": None,
        "vram_total_mib": total,
        "vram_free_mib": (gpu_state or {}).get("vram_free_mib"),
    }


def gather_recovery_evidence(
    *,
    model: str,
    task_type: str,
    failure_type: str,
    current_context: int,
    candidate_context: int,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """P2-9 observations から判断材料を収集。"""
    rows = observations if observations is not None else load_observations()

    def _match(row: dict[str, Any]) -> bool:
        ex = row.get("execution") or {}
        if ex.get("model") and ex.get("model") != model:
            return False
        if task_type and task_type != "unknown" and ex.get("task_type") != task_type:
            return False
        return True

    matched = [r for r in rows if _match(r)]

    def _ctx_rows(ctx: int) -> list[dict[str, Any]]:
        return [
            r
            for r in matched
            if (r.get("execution") or {}).get("context_size") == ctx
        ]

    current_rows = _ctx_rows(current_context)
    candidate_rows = _ctx_rows(candidate_context)

    def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
        if not rows:
            return None
        hits = sum(1 for r in rows if (r.get("outcome") or {}).get(key))
        return round(hits / len(rows), 4)

    cur_success = _rate(current_rows, "success")
    cand_success = _rate(candidate_rows, "success")
    cand_native = _rate(candidate_rows, "native_tool_call")
    cur_native = _rate(current_rows, "native_tool_call")

    improvement = None
    if cur_success is not None and cand_success is not None:
        improvement = round(cand_success - cur_success, 4)

    return {
        "failure_type": failure_type,
        "current_context_observations": len(current_rows),
        "candidate_context_observations": len(candidate_rows),
        "current_success_rate": cur_success,
        "candidate_success_rate": cand_success,
        "current_native_tool_call_rate": cur_native,
        "candidate_native_tool_call_rate": cand_native,
        "success_rate_improvement": improvement,
        "historical_improvement_observed": (
            improvement is not None and improvement > 0 and len(candidate_rows) >= 1
        ),
    }


def compute_confidence(evidence: dict[str, Any], policy: dict[str, Any] | None = None) -> str:
    policy = policy or load_recovery_policy()
    cfg = policy.get("evidence_confidence") or {}
    n = evidence.get("candidate_context_observations") or 0
    improvement = evidence.get("success_rate_improvement")
    threshold = cfg.get("improvement_rate_threshold", 0.15)

    if n >= cfg.get("high_min_candidate_observations", 10):
        if improvement is not None and improvement >= threshold:
            return "HIGH"
        return "MEDIUM"
    if n >= cfg.get("medium_min_candidate_observations", 5):
        if improvement is not None and improvement > 0:
            return "MEDIUM"
        return "LOW"
    if n >= cfg.get("low_min_candidate_observations", 1):
        return "LOW"
    return "UNKNOWN"


def build_recovery_decision(
    *,
    parent_execution_id: str,
    model: str,
    profile_id: str | None,
    configured_context: int,
    current_context: int,
    failure_type: str,
    task_type: str = "unknown",
    scenario_id: str | None = None,
    candidate_strategy: str = "increase_context",
    candidate_context: int | None = None,
    gpu_state: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    attempt_number: int = 1,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_recovery_policy()
    reasons: list[str] = []

    if failure_type == "TOOL_CALL_NOT_GENERATED":
        reasons.append("Native Tool Call が生成されなかった")
    elif failure_type == "TIMEOUT":
        reasons.append("LLM 実行が timeout した")
    elif failure_type == "CONTEXT_LIMIT":
        reasons.append("Context 上限に関連する失敗")
    else:
        reasons.append(f"failure_type={failure_type}")

    if candidate_context is None and candidate_strategy == "increase_context":
        candidate_context = next_context_step(current_context, policy)

    validation = (
        validate_candidate_context(
            int(candidate_context),
            current=current_context,
            model=model,
            profile_id=profile_id,
            policy=policy,
        )
        if candidate_context is not None
        else {"valid": False, "reasons": ["no candidate context"]}
    )

    if not validation.get("valid"):
        candidate_strategy = "none"
        reasons.extend(validation.get("reasons") or [])

    if evidence is None and candidate_context is not None and validation.get("valid"):
        evidence = gather_recovery_evidence(
            model=model,
            task_type=task_type,
            failure_type=failure_type,
            current_context=current_context,
            candidate_context=int(candidate_context),
        )
        if evidence.get("historical_improvement_observed"):
            reasons.append("過去の実測で Context 増加時に改善が観測されている")

    confidence = compute_confidence(evidence or {}, policy) if candidate_strategy != "none" else "UNKNOWN"

    gpu_check = gpu_observation_allows_execution(gpu_state, policy)
    auto_allowed = is_automatic_recovery_enabled(policy)
    execution_allowed = (
        candidate_strategy != "none"
        and validation.get("valid")
        and gpu_check.get("execution_allowed", False)
        and attempt_number <= int(policy.get("max_recovery_attempts", 1))
    )

    return {
        "schema_version": 1,
        "recovery_id": str(uuid.uuid4()),
        "timestamp": _utc_now_iso(),
        "parent_execution_id": parent_execution_id,
        "model": model,
        "profile_id": profile_id,
        "configured_context": configured_context,
        "current_context": current_context,
        "failure_type": failure_type,
        "task_type": task_type,
        "scenario_id": scenario_id,
        "candidate_strategy": candidate_strategy,
        "candidate_context": candidate_context if candidate_strategy != "none" else None,
        "confidence": confidence,
        "reason": reasons,
        "evidence": evidence or {},
        "gpu_state": gpu_state,
        "gpu_execution_check": gpu_check,
        "validation": validation,
        "automatic_execution_allowed": auto_allowed and execution_allowed,
        "execution_allowed": execution_allowed,
        "attempt_number": attempt_number,
        "note": "automatic_execution_allowed=false がデフォルト。明示承認後のみ retry。",
    }


def propose_recovery(
    execution: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    session: RecoverySession | None = None,
) -> dict[str, Any]:
    """失敗 execution から Recovery 候補を生成。成功時は recovery=none。"""
    policy = policy or load_recovery_policy()
    classification = execution.get("failure_classification")
    if not classification:
        classification = classify_execution_record(execution)

    if not execution_needs_recovery(classification):
        return {
            "recovery_required": False,
            "failure_classification": classification,
            "decisions": [],
        }

    failure_type = classification["failure_type"]
    allowed_types = policy.get("increase_context_failure_types") or []
    if failure_type not in allowed_types:
        return {
            "recovery_required": True,
            "failure_classification": classification,
            "decisions": [],
            "note": f"failure_type {failure_type} has no configured strategy",
        }

    session = session or RecoverySession(policy=policy)
    if not session.can_attempt_recovery():
        return {
            "recovery_required": True,
            "failure_classification": classification,
            "decisions": [],
            "note": "max recovery attempts reached",
        }

    configured = execution.get("configured_context") or get_configured_context()
    current = execution.get("runtime_context") or execution.get("context_size") or configured
    gpu_state = execution.get("gpu_state")
    if gpu_state is None:
        try:
            gpu_state = snapshot_gpu()
        except Exception:
            gpu_state = {"capture_error": True}

    decision = build_recovery_decision(
        parent_execution_id=execution.get("execution_id") or str(uuid.uuid4()),
        model=str(execution.get("model") or get_llm_profile().get("model")),
        profile_id=execution.get("profile_id") or get_llm_profile().get("id"),
        configured_context=int(configured) if configured else int(current),
        current_context=int(current),
        failure_type=failure_type,
        task_type=execution.get("task_type") or "unknown",
        scenario_id=execution.get("scenario_id"),
        gpu_state=gpu_state,
        attempt_number=session.next_attempt_number(),
        policy=policy,
    )
    return {
        "recovery_required": True,
        "failure_classification": classification,
        "decisions": [decision],
    }


def propose_all_recovery_candidates(
    execution: dict[str, Any],
    *,
    search_payload: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    session: RecoverySession | None = None,
) -> dict[str, Any]:
    """比較実験用: 複数 Strategy の Recovery 候補を生成（自動実行なし）。"""
    policy = policy or load_recovery_policy()
    classification = execution.get("failure_classification")
    if not classification:
        classification = classify_execution_record(execution)

    session = session or RecoverySession(policy=policy)
    configured = execution.get("configured_context") or get_configured_context()
    current = execution.get("runtime_context") or execution.get("context_size") or configured
    failure_type = classification.get("failure_type") or "UNKNOWN"

    try:
        gpu_state = execution.get("gpu_state") or snapshot_gpu()
    except Exception:
        gpu_state = {"capture_error": True}

    strategies = list(policy.get("compare_strategies") or [])
    decisions: list[dict[str, Any]] = []
    parent_id = execution.get("execution_id") or str(uuid.uuid4())

    for strategy in strategies:
        candidate_ctx = int(current)
        reasons = [f"strategy={strategy}"]
        if strategy == "increase_context":
            candidate_ctx = next_context_step(int(current), policy) or int(current)
            reasons.append("Context を一段階増加")
        elif strategy == "retry_same_context":
            reasons.append("同一 Context で再試行")
        elif strategy == "reduce_tool_result":
            max_m = (policy.get("strategy_params") or {}).get("reduce_tool_result", {}).get(
                "max_matches", 10
            )
            reasons.append(f"Tool Result を上位 {max_m} 件に削減")
        elif strategy == "narrow_search_scope":
            reasons.append("検索範囲を狭めて再検索")
        elif strategy == "retry_with_explicit_tool_instruction":
            reasons.append("Native Tool Call 生成を明示指示")

        validation = validate_candidate_context(
            candidate_ctx,
            current=int(current),
            model=str(execution.get("model") or get_llm_profile().get("model")),
            profile_id=execution.get("profile_id"),
            policy=policy,
        ) if strategy == "increase_context" else {"valid": True, "reasons": []}

        if strategy != "increase_context":
            validation = {"valid": True, "reasons": [], "candidate_context": candidate_ctx}

        if strategy == "increase_context" and not validation.get("valid"):
            continue

        evidence = None
        if strategy == "increase_context" and validation.get("valid"):
            evidence = gather_recovery_evidence(
                model=str(execution.get("model") or get_llm_profile().get("model")),
                task_type=execution.get("task_type") or "search_read",
                failure_type=failure_type,
                current_context=int(current),
                candidate_context=int(candidate_ctx),
            )
            if evidence:
                evidence["evidence_source"] = "legacy_observation"

        gpu_check = gpu_observation_allows_execution(gpu_state, policy)
        execution_allowed = validation.get("valid") and gpu_check.get("execution_allowed", False)

        decisions.append(
            {
                "schema_version": 1,
                "recovery_id": str(uuid.uuid4()),
                "timestamp": _utc_now_iso(),
                "parent_execution_id": parent_id,
                "model": execution.get("model"),
                "profile_id": execution.get("profile_id"),
                "configured_context": configured,
                "current_context": current,
                "failure_type": failure_type,
                "task_type": execution.get("task_type") or "search_read",
                "scenario_id": execution.get("scenario_id"),
                "candidate_strategy": strategy,
                "candidate_context": candidate_ctx if strategy == "increase_context" else current,
                "confidence": compute_confidence(evidence or {}, policy) if evidence else "UNKNOWN",
                "reason": reasons,
                "evidence": evidence or {},
                "gpu_state": gpu_state,
                "gpu_execution_check": gpu_check,
                "validation": validation,
                "automatic_execution_allowed": False,
                "execution_allowed": execution_allowed,
                "attempt_number": session.next_attempt_number(),
                "search_payload_metrics": (
                    {
                        "match_count": search_payload.get("match_count"),
                        "truncated": search_payload.get("truncated"),
                    }
                    if search_payload
                    else None
                ),
            }
        )

    return {
        "recovery_required": execution_needs_recovery(classification),
        "failure_classification": classification,
        "decisions": decisions,
        "note": "comparison candidates; explicit approval required for each strategy",
    }


def recommend_recovery_strategies(
    execution: dict[str, Any],
    *,
    search_payload: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    session: RecoverySession | None = None,
    import_p11_evidence: bool = True,
    cycle_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Failure → Situation Analysis → Candidates → Evidence-based Ranking.
    increase_context は通常候補から分離し Context Expansion Gate で管理（P2-13）。
    自動実行なし。順位付き recommendation を返す。
    """
    from tools.system.context_monitor.context_expansion_gate import evaluate_context_expansion_gate
    from tools.system.context_monitor.recovery_evidence import (
        import_p11_compare_evidence,
        load_strategy_evidence,
        summarize_strategy_evidence,
    )
    from tools.system.context_monitor.recovery_ranking import (
        analyze_situation,
        build_recommendation_summary,
        rank_recovery_candidates,
    )

    policy = policy or load_recovery_policy()
    session = session or RecoverySession(policy=policy)
    if import_p11_evidence:
        import_p11_compare_evidence(skip_if_imported=True)

    proposal = propose_all_recovery_candidates(
        execution,
        search_payload=search_payload,
        policy=policy,
        session=session,
    )
    gpu_state = execution.get("gpu_state")
    situation = analyze_situation(
        execution,
        search_payload=search_payload,
        gpu_state=gpu_state,
        policy=policy,
    )
    evidence = load_strategy_evidence()

    all_decisions = proposal.get("decisions") or []
    normal_decisions = [
        d for d in all_decisions if d.get("candidate_strategy") != "increase_context"
    ]
    ctx_decision = next(
        (d for d in all_decisions if d.get("candidate_strategy") == "increase_context"),
        None,
    )

    ranked = rank_recovery_candidates(
        normal_decisions,
        situation,
        evidence,
        policy,
    )

    ctx_gate = evaluate_context_expansion_gate(
        execution=execution,
        cycle_state=cycle_state,
        context_expansion_decision=ctx_decision,
        normal_recommendations=ranked,
        policy=policy,
        session=session,
        human_approved=False,
        check_approval=False,
    )
    context_expansion = {
        "strategy": "increase_context",
        "gate_status": ctx_gate.get("gate_status"),
        "blocked_reasons": ctx_gate.get("blocked_reasons"),
        "candidate_context": ctx_gate.get("candidate_context"),
        "decision": ctx_decision,
        "validation": ctx_gate.get("validation"),
        "gpu_execution_check": ctx_gate.get("gpu_execution_check"),
        "note": "last-resort; not included in normal ranking",
    }

    return {
        "recovery_required": proposal.get("recovery_required"),
        "failure_classification": proposal.get("failure_classification"),
        "situation": situation,
        "normal_recommendations": ranked,
        "recommendations": ranked,
        "context_expansion": context_expansion,
        "recommendation_summary": build_recommendation_summary(ranked),
        "automatic_recovery_enabled": is_automatic_recovery_enabled(policy),
        "evidence_summary": summarize_strategy_evidence(evidence),
        "note": "candidate recommendation only; increase_context gated separately; explicit approval required",
    }


class RecoverySession:
    """同一条件での Retry / Context 変更回数を制限。"""

    def __init__(self, policy: dict[str, Any] | None = None):
        self._policy = policy or load_recovery_policy()
        self._attempts = 0
        self._context_changes = 0
        self._context_history: list[int] = []

    def can_attempt_recovery(self) -> bool:
        return self._attempts < int(self._policy.get("max_recovery_attempts", 1))

    def can_change_context(self, new_context: int) -> bool:
        max_changes = int(self._policy.get("max_context_changes_per_session", 1))
        if self._context_changes >= max_changes:
            return False
        if self._context_history and new_context <= self._context_history[-1]:
            return False
        if new_context in self._context_history:
            return False
        return True

    def next_attempt_number(self) -> int:
        return self._attempts + 1

    def record_attempt(self, *, context_used: int | None = None) -> None:
        self._attempts += 1
        if context_used is not None:
            if self._context_history and context_used != self._context_history[-1]:
                self._context_changes += 1
            elif not self._context_history:
                self._context_changes += 1
            self._context_history.append(context_used)


def append_recovery_decision(decision: dict[str, Any], *, path=None) -> str:
    ensure_monitor_dir()
    target = path or RECOVERY_DECISIONS_JSONL
    rid = decision.get("recovery_id") or str(uuid.uuid4())
    decision["recovery_id"] = rid
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    return rid


def append_recovery_result(result: dict[str, Any], *, path=None) -> str:
    ensure_monitor_dir()
    target = path or RECOVERY_RESULTS_JSONL
    rid = result.get("recovery_result_id") or str(uuid.uuid4())
    result["recovery_result_id"] = rid
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    return rid


def build_execution_record(
    *,
    execution_id: str | None = None,
    model: str | None = None,
    profile_id: str | None = None,
    configured_context: int | None = None,
    runtime_context: int | None = None,
    task_type: str = "unknown",
    scenario_id: str | None = None,
    response: Any | None = None,
    expected_tool: str | None = None,
    tool_execution_ok: bool | None = None,
    timeout: bool = False,
    error: str | None = None,
    gpu_state: dict[str, Any] | None = None,
    elapsed_ms: int | None = None,
    tools_requested: bool = True,
) -> dict[str, Any]:
    """execution_result / task_result / recovery_result を分離した実行記録。"""
    profile = get_llm_profile()
    configured = configured_context if configured_context is not None else get_configured_context(profile)
    runtime = runtime_context if runtime_context is not None else configured

    classification = classify_llm_response(
        response,
        expected_tool=expected_tool,
        tools_requested=tools_requested,
        tool_execution_ok=tool_execution_ok,
        timeout=timeout,
        error=error,
    )

    native_names: list[str] = []
    if response is not None:
        try:
            msg = getattr(response, "message", None)
            tcs = getattr(msg, "tool_calls", None) or []
            native_names = [tc.function.name for tc in tcs if getattr(getattr(tc, "function", None), "name", None)]
        except Exception:
            pass

    exec_result = classification["execution_result"]
    return {
        "execution_id": execution_id or str(uuid.uuid4()),
        "timestamp": _utc_now_iso(),
        "execution_result": exec_result,
        "task_result": None,
        "failure_classification": classification,
        "model": model or profile.get("model"),
        "profile_id": profile_id or profile.get("id"),
        "configured_context": configured,
        "runtime_context": runtime,
        "context_size": runtime,
        "task_type": task_type,
        "scenario_id": scenario_id,
        "expected_tool": expected_tool,
        "tools_requested": tools_requested,
        "tool_execution_ok": tool_execution_ok,
        "timeout": timeout,
        "error": error,
        "native_tool_call": bool(native_names),
        "native_tool_names": native_names,
        "gpu_state": gpu_state,
        "elapsed_ms": elapsed_ms,
    }


def execute_recovery_retry(
    decision: dict[str, Any],
    chat_fn: Callable[..., Any],
    *,
    chat_kwargs: dict[str, Any],
    approved: bool = False,
    session: RecoverySession | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """明示承認後のみ再試行。yaml の configured_context は変更しない。"""
    policy = load_recovery_policy()
    session = session or RecoverySession(policy=policy)

    if not approved:
        return {
            "recovery_result": "not_executed",
            "reason": "explicit approval required",
            "decision": decision,
        }

    if is_automatic_recovery_enabled(policy) and not decision.get("automatic_execution_allowed"):
        if not approved:
            return {"recovery_result": "not_executed", "reason": "automatic recovery disabled"}

    if not decision.get("execution_allowed"):
        return {
            "recovery_result": "not_executed",
            "reason": "execution not allowed",
            "decision": decision,
        }

    candidate_ctx = decision.get("candidate_context")
    if candidate_ctx is None:
        return {"recovery_result": "not_executed", "reason": "no candidate context"}

    if not session.can_change_context(int(candidate_ctx)):
        return {"recovery_result": "not_executed", "reason": "context change limit reached"}

    if record:
        append_recovery_decision(decision)

    started = datetime.now(timezone.utc)
    gpu_before = snapshot_gpu()
    err = None
    response = None
    timeout = False
    try:
        response = chat_fn(**chat_kwargs, runtime_context=int(candidate_ctx))
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        timeout = "timeout" in err.lower()
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    gpu_after = snapshot_gpu()

    retry_execution = build_execution_record(
        execution_id=str(uuid.uuid4()),
        model=decision.get("model"),
        profile_id=decision.get("profile_id"),
        configured_context=decision.get("configured_context"),
        runtime_context=int(candidate_ctx),
        task_type=decision.get("task_type") or "unknown",
        scenario_id=decision.get("scenario_id"),
        response=response,
        expected_tool=chat_kwargs.get("expected_tool"),
        tool_execution_ok=chat_kwargs.get("tool_execution_ok"),
        timeout=timeout,
        error=err,
        gpu_state=gpu_before,
        elapsed_ms=elapsed_ms,
    )

    session.record_attempt(context_used=int(candidate_ctx))

    recovery_result = {
        "schema_version": 1,
        "timestamp": _utc_now_iso(),
        "parent_execution_id": decision.get("parent_execution_id"),
        "recovery_id": decision.get("recovery_id"),
        "attempt_number": decision.get("attempt_number"),
        "previous_context": decision.get("current_context"),
        "current_context": candidate_ctx,
        "configured_context": decision.get("configured_context"),
        "failure_type": decision.get("failure_type"),
        "candidate_strategy": decision.get("candidate_strategy"),
        "recovery_result": (
            "success" if retry_execution["execution_result"] == "success" else "failure"
        ),
        "execution_result": retry_execution["execution_result"],
        "retry_execution_id": retry_execution["execution_id"],
        "retry_execution": retry_execution,
        "tool_call_generated": retry_execution.get("native_tool_call"),
        "tool_execution_success": chat_kwargs.get("tool_execution_ok"),
        "latency_ms": elapsed_ms,
        "timeout": timeout,
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "confidence": decision.get("confidence"),
        "validation": "provisional",
    }

    if record:
        append_recovery_result(recovery_result)
        append_observation(
            build_observation(
                source="recovery.retry",
                model=retry_execution.get("model"),
                profile_id=retry_execution.get("profile_id"),
                context_size=int(candidate_ctx),
                tools_enabled=bool(chat_kwargs.get("tools")),
                task_type=decision.get("task_type"),
                scenario_id=decision.get("scenario_id"),
                execution_id=retry_execution["execution_id"],
                gpu_before=gpu_before,
                gpu_after=gpu_after,
                outcome={
                    "success": retry_execution["execution_result"] == "success",
                    "timeout": timeout,
                    "native_tool_call": retry_execution.get("native_tool_call"),
                    "native_tool_names": retry_execution.get("native_tool_names"),
                    "recovery_id": decision.get("recovery_id"),
                    "parent_execution_id": decision.get("parent_execution_id"),
                },
                performance={"elapsed_ms": elapsed_ms},
                limits={
                    "configured_context_limit": decision.get("configured_context"),
                    "runtime_context": int(candidate_ctx),
                    "recovery_attempt": decision.get("attempt_number"),
                },
            )
        )

    return recovery_result
