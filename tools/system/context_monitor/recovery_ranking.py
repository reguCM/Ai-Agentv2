"""Recovery Strategy Evidence ベース順位付け（固定順位なし）。"""
from __future__ import annotations

from typing import Any

from tools.system.context_monitor.recovery_evidence import (
    load_strategy_evidence,
    query_strategy_evidence,
    summarize_strategy_evidence,
)


def analyze_situation(
    execution: dict[str, Any],
    *,
    search_payload: dict[str, Any] | None = None,
    gpu_state: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Failure + Tool Result + Context + GPU の状況分析（評価ではなく事実+フラグ）。"""
    policy = policy or {}
    thresholds = policy.get("situation_thresholds") or {}
    gpu_obs = policy.get("gpu_ranking_observation") or {}
    large_count = int(thresholds.get("large_result_match_count") or 30)
    large_bytes = int(thresholds.get("large_payload_bytes") or 8000)
    vram_tight = int(gpu_obs.get("vram_free_tight_mib") or 600)

    classification = execution.get("failure_classification") or {}
    failure_type = classification.get("failure_type") or execution.get("failure_type") or "UNKNOWN"
    sp = search_payload or execution.get("search_payload_metrics") or {}
    match_count = sp.get("match_count") or execution.get("tool_result_count")
    payload_bytes = sp.get("payload_bytes") or execution.get("payload_bytes")
    truncated = sp.get("truncated") if sp.get("truncated") is not None else execution.get("truncated")

    gpu = gpu_state or execution.get("gpu_state") or {}
    vram_free = gpu.get("vram_free_mib")
    if vram_free is None:
        status = gpu.get("gpu_status") or {}
        used, total = status.get("vram_used"), status.get("vram_total")
        if isinstance(used, int) and isinstance(total, int):
            vram_free = total - used

    configured = execution.get("configured_context") or execution.get("context_size")
    runtime = execution.get("runtime_context") or configured

    flags: dict[str, bool] = {
        "large_tool_result": isinstance(match_count, int) and match_count >= large_count,
        "large_payload": isinstance(payload_bytes, int) and payload_bytes >= large_bytes,
        "truncated_result": bool(truncated),
        "timeout_failure": failure_type == "TIMEOUT",
        "tool_call_not_generated": failure_type == "TOOL_CALL_NOT_GENERATED",
        "context_limit_failure": failure_type == "CONTEXT_LIMIT",
        "gpu_vram_tight_observation": isinstance(vram_free, int) and vram_free < vram_tight,
    }

    return {
        "failure_type": failure_type,
        "configured_context": configured,
        "runtime_context": runtime,
        "tool_result_count": match_count,
        "payload_bytes": payload_bytes,
        "truncated": truncated,
        "vram_free_mib": vram_free,
        "flags": flags,
    }


def _confidence_from_evidence_count(count: int, policy: dict[str, Any]) -> str:
    cfg = policy.get("evidence_confidence") or {}
    if count >= cfg.get("high_min_candidate_observations", 10):
        return "HIGH"
    if count >= cfg.get("medium_min_candidate_observations", 5):
        return "MEDIUM"
    if count >= cfg.get("low_min_candidate_observations", 1):
        return "LOW"
    return "UNKNOWN"


def score_strategy(
    strategy: str,
    situation: dict[str, Any],
    evidence: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Policy signals + Evidence からスコア（固定順位ではない）。"""
    signals = (policy.get("ranking_signals") or {}).get(strategy) or {}
    flags = situation.get("flags") or {}
    score = float(signals.get("base_score") or 0)
    reasons: list[str] = []
    factors: dict[str, Any] = {"base_score": score}

    for flag_name, delta in (signals.get("flag_adjustments") or {}).items():
        if flags.get(flag_name):
            score += float(delta)
            reasons.append(f"flag:{flag_name} ({delta:+.0f})")
            factors[f"flag_{flag_name}"] = delta

    ft = situation.get("failure_type")
    matched = query_strategy_evidence(
        evidence,
        strategy=strategy,
        failure_type=ft,
        min_match_count=int(situation["tool_result_count"]) if flags.get("large_tool_result") and situation.get("tool_result_count") else None,
        truncated=situation.get("truncated") if flags.get("truncated_result") else None,
    )
    if not matched and ft:
        matched = query_strategy_evidence(evidence, strategy=strategy, failure_type=ft)

    ev_summary = summarize_strategy_evidence(matched) if matched else {}
    strat_ev = ev_summary.get(strategy) or {}
    ev_count = strat_ev.get("evidence_count") or len([r for r in matched if r.get("phase") == "recovery"])
    factors["evidence_count"] = ev_count

    ev_adj = signals.get("evidence_adjustments") or {}
    if ev_count > 0:
        rate = strat_ev.get("tool_call_success_rate")
        if rate is not None and rate >= 0.5:
            bonus = float(ev_adj.get("success_rate_gte_0_5") or 15)
            score += bonus
            reasons.append(f"historical tool_call_success_rate={rate} (+{bonus})")
            factors["evidence_success_bonus"] = bonus
        elif rate is not None and rate == 0:
            penalty = float(ev_adj.get("success_rate_eq_0") or -20)
            score += penalty
            reasons.append(f"historical tool_call_success_rate=0 ({penalty:+.0f})")
            factors["evidence_failure_penalty"] = penalty

        avg_lat = strat_ev.get("avg_latency_ms")
        if avg_lat is not None and avg_lat > 60000:
            penalty = float(ev_adj.get("avg_latency_over_60s") or -10)
            score += penalty
            reasons.append(f"historical avg_latency_ms={avg_lat} ({penalty:+.0f})")
            factors["latency_penalty"] = penalty

    if strategy == "increase_context":
        inc_rows = query_strategy_evidence(evidence, strategy="increase_context")
        if inc_rows:
            fails = sum(1 for r in inc_rows if not r.get("tool_call_success"))
            if fails > 0 and flags.get("large_tool_result"):
                penalty = float(ev_adj.get("increase_failed_with_large_result") or -25)
                score += penalty
                reasons.append(
                    f"increase_context failed with large tool result in evidence ({penalty:+.0f})"
                )
                factors["increase_large_result_penalty"] = penalty

    if strategy == "retry_same_context" and flags.get("timeout_failure"):
        penalty = float(signals.get("timeout_retry_penalty") or -20)
        score += penalty
        reasons.append(f"timeout failure: retry_same_context deprioritized ({penalty:+.0f})")
        factors["timeout_retry_penalty"] = penalty

    confidence = _confidence_from_evidence_count(ev_count, policy)
    if ev_count < 3 and confidence == "HIGH":
        confidence = "MEDIUM"
    if ev_count == 0:
        confidence = "UNKNOWN"

    return {
        "strategy": strategy,
        "rank_score": round(score, 2),
        "recommendation_reasons": reasons,
        "priority_factors": factors,
        "evidence_count": ev_count,
        "confidence": confidence,
        "historical_summary": strat_ev if strat_ev else None,
    }


def rank_recovery_candidates(
    decisions: list[dict[str, Any]],
    situation: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """候補をスコア順に並べ替え（同点は strategy 名で安定ソート）。"""
    policy = policy or {}
    evidence = evidence if evidence is not None else load_strategy_evidence()
    ranked: list[dict[str, Any]] = []

    for decision in decisions:
        strategy = decision.get("candidate_strategy") or ""
        scoring = score_strategy(strategy, situation, evidence, policy)
        merged = {
            **decision,
            "strategy_rank": None,
            "rank_score": scoring["rank_score"],
            "recommendation_reasons": scoring["recommendation_reasons"],
            "priority_factors": scoring["priority_factors"],
            "evidence_count": scoring["evidence_count"],
            "confidence": scoring["confidence"],
            "historical_summary": scoring.get("historical_summary"),
            "automatic_execution_allowed": False,
        }
        ranked.append(merged)

    ranked.sort(key=lambda x: (-float(x.get("rank_score") or 0), str(x.get("candidate_strategy"))))
    for i, row in enumerate(ranked, start=1):
        row["strategy_rank"] = i
    return ranked


def build_recommendation_summary(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agent / CLI 向け簡易サマリ。"""
    out: list[dict[str, Any]] = []
    for row in ranked:
        out.append(
            {
                "rank": row.get("strategy_rank"),
                "strategy": row.get("candidate_strategy"),
                "rank_score": row.get("rank_score"),
                "confidence": row.get("confidence"),
                "evidence_count": row.get("evidence_count"),
                "reasons": row.get("recommendation_reasons") or row.get("reason") or [],
                "candidate_context": row.get("candidate_context"),
                "execution_allowed": row.get("execution_allowed"),
            }
        )
    return out
