"""Recovery Strategy 比較実験 Harness (P2-11)。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tools.file.workspace.search_files import search_files
from tools.system.config import get_llm_profile
from tools.system.context_monitor.paths import HARNESS_RUNS_DIR, ensure_monitor_dir
from tools.system.context_monitor.recovery import (
    RecoverySession,
    append_recovery_decision,
    append_recovery_result,
    get_configured_context,
    load_recovery_policy,
    recommend_recovery_strategies,
)
from tools.system.context_monitor.recovery_harness import (
    EXPECTED_TOOL,
    _needs_recovery,
    run_llm_attempt,
)
from tools.system.context_monitor.recovery_evidence import record_strategy_outcome
from tools.system.context_monitor.recovery_strategies import (
    COMPARE_STRATEGIES,
    apply_strategy,
    payload_metrics,
)

TASK_ID = "FILE-TOOLS-RECOVERY-STRATEGY-COMPARE-P2-11"
EVIDENCE_SOURCE = "p2-11_live_strategy_compare"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _attempt_metrics(attempt: dict[str, Any]) -> dict[str, Any]:
    ex = attempt.get("execution") or {}
    return {
        "strategy": attempt.get("strategy"),
        "context": attempt.get("runtime_context"),
        "execution_result": ex.get("execution_result"),
        "failure_type": (ex.get("failure_classification") or {}).get("failure_type"),
        "tool_call_recovery": ex.get("tool_call_recovery"),
        "task_result": ex.get("task_result"),
        "tool_call_generated": ex.get("native_tool_call"),
        "tool_execution_success": ex.get("tool_execution_ok"),
        "timeout": attempt.get("timeout"),
        "latency_ms": attempt.get("elapsed_ms"),
        "result_count": attempt.get("result_count"),
        "payload_bytes": attempt.get("payload_bytes"),
        "truncated": attempt.get("truncated"),
        "gpu_before": attempt.get("gpu_before"),
        "gpu_after": attempt.get("gpu_after"),
        "vram_free_before_mib": (attempt.get("gpu_before") or {}).get("vram_free_mib"),
        "vram_free_after_mib": (attempt.get("gpu_after") or {}).get("vram_free_mib"),
    }


def run_strategy_attempt(
    strategy: str,
    *,
    search_payload: dict[str, Any],
    scenario_id: str,
    chat_fn: Callable[..., Any] | None = None,
    policy: dict[str, Any] | None = None,
    parent_execution_id: str | None = None,
) -> dict[str, Any]:
    """単一 Strategy を明示実行。"""
    policy = policy or load_recovery_policy()
    configured = get_configured_context()
    applied = apply_strategy(
        strategy,
        search_payload=search_payload,
        configured_context=int(configured),
        policy=policy,
    )
    attempt = run_llm_attempt(
        applied["messages"],
        applied["meta"]["llm_tools"],
        runtime_context=int(applied["runtime_context"]),
        scenario_id=f"{scenario_id}_{strategy}",
        chat_fn=chat_fn,
    )
    ex = attempt["execution"]
    record = {
        "strategy": strategy,
        "scenario_id": scenario_id,
        "parent_execution_id": parent_execution_id,
        "runtime_context": applied["runtime_context"],
        "configured_context": configured,
        "strategy_params": applied["strategy_params"],
        "execution": ex,
        "timeout": attempt.get("timeout"),
        "elapsed_ms": attempt.get("elapsed_ms"),
        "gpu_before": attempt.get("gpu_before"),
        "gpu_after": attempt.get("gpu_after"),
        **payload_metrics(applied["search_payload"]),
        "evidence_source": EVIDENCE_SOURCE,
    }
    return record


def run_compare_cycle(
    *,
    scenario_id: str,
    search_payload: dict[str, Any] | None = None,
    strategies: list[str] | None = None,
    chat_fn: Callable[..., Any] | None = None,
    execute_strategies: bool = True,
) -> dict[str, Any]:
    """
    1サイクル: baseline (16384) → 各 Strategy 比較。
    baseline 失敗/成功に関わらず全 Strategy を同一条件起点で実行可能。
    """
    policy = load_recovery_policy()
    configured = get_configured_context()
    if search_payload is None:
        search_payload = search_files("read_file", path=".")

    baseline_applied = apply_strategy(
        "retry_same_context",
        search_payload=search_payload,
        configured_context=int(configured),
        policy=policy,
    )
    baseline = run_llm_attempt(
        baseline_applied["messages"],
        baseline_applied["meta"]["llm_tools"],
        runtime_context=int(configured),
        scenario_id=f"{scenario_id}_baseline",
        chat_fn=chat_fn,
    )
    baseline_exec = baseline["execution"]
    baseline_needs_recovery = _needs_recovery(baseline_exec, expected_tool=EXPECTED_TOOL)

    cycle: dict[str, Any] = {
        "scenario_id": scenario_id,
        "task_type": "search_read",
        "model": baseline_exec.get("model"),
        "configured_context": configured,
        "baseline_search_payload": payload_metrics(search_payload),
        "baseline": {
            "label": "initial_16384",
            **_attempt_metrics(
                {
                    "strategy": "baseline",
                    "runtime_context": configured,
                    "execution": baseline_exec,
                    "timeout": baseline.get("timeout"),
                    "elapsed_ms": baseline.get("elapsed_ms"),
                    "gpu_before": baseline.get("gpu_before"),
                    "gpu_after": baseline.get("gpu_after"),
                    **payload_metrics(search_payload),
                }
            ),
            "execution_id": baseline_exec.get("execution_id"),
            "failure_reproduced": baseline_needs_recovery,
        },
        "recovery_candidates": [],
        "strategies": {},
        "evidence_source": EVIDENCE_SOURCE,
    }

    recommendation = recommend_recovery_strategies(
        baseline_exec,
        search_payload=search_payload,
        session=RecoverySession(policy=policy),
    )
    cycle["recovery_candidates"] = recommendation.get("recommendations") or []
    cycle["recovery_recommendation"] = {
        "situation": recommendation.get("situation"),
        "recommendation_summary": recommendation.get("recommendation_summary"),
        "evidence_summary": recommendation.get("evidence_summary"),
    }
    cycle["baseline"]["failure_classification"] = baseline_exec.get("failure_classification")

    if not execute_strategies:
        return cycle

    strat_list = strategies or list(policy.get("compare_strategies") or COMPARE_STRATEGIES)
    for strategy in strat_list:
        print(f"  strategy {strategy}...", flush=True)
        try:
            record = run_strategy_attempt(
                strategy,
                search_payload=search_payload,
                scenario_id=scenario_id,
                chat_fn=chat_fn,
                policy=policy,
                parent_execution_id=baseline_exec.get("execution_id"),
            )
            cycle["strategies"][strategy] = _attempt_metrics(record)
            cycle["strategies"][strategy]["execution_id"] = (record.get("execution") or {}).get(
                "execution_id"
            )
            cycle["strategies"][strategy]["strategy_params"] = record.get("strategy_params")
            if strategy != "retry_same_context" or baseline_needs_recovery:
                decision = next(
                    (d for d in cycle["recovery_candidates"] if d.get("candidate_strategy") == strategy),
                    None,
                )
                if decision:
                    append_recovery_decision(decision)
                append_recovery_result(
                    {
                        "schema_version": 1,
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "parent_execution_id": baseline_exec.get("execution_id"),
                        "recovery_id": (decision or {}).get("recovery_id"),
                        "candidate_strategy": strategy,
                        "recovery_result": record.get("execution", {}).get("tool_call_recovery"),
                        "tool_call_recovery": record.get("execution", {}).get("tool_call_recovery"),
                        "latency_ms": record.get("elapsed_ms"),
                        "evidence_source": EVIDENCE_SOURCE,
                    }
                )
                metrics = cycle["strategies"][strategy]
                fc = baseline_exec.get("failure_classification") or {}
                tc_ok = metrics.get("tool_call_recovery") == "SUCCESS"
                record_strategy_outcome(
                    strategy=strategy,
                    failure_type=fc.get("failure_type"),
                    configured_context=configured,
                    runtime_context=metrics.get("context") or record.get("runtime_context"),
                    tool_result_count=metrics.get("result_count"),
                    payload_bytes=metrics.get("payload_bytes"),
                    truncated=metrics.get("truncated"),
                    tool_call_success=tc_ok,
                    tool_execution_success=metrics.get("tool_execution_success"),
                    timeout=metrics.get("timeout"),
                    latency_ms=metrics.get("latency_ms"),
                    gpu_before=record.get("gpu_before"),
                    gpu_after=record.get("gpu_after"),
                    recovery_result="success" if tc_ok else "failure",
                    scenario_id=scenario_id,
                    evidence_source=EVIDENCE_SOURCE,
                    extra={"parent_execution_id": baseline_exec.get("execution_id")},
                )
        except Exception as exc:  # noqa: BLE001
            cycle["strategies"][strategy] = {
                "strategy": strategy,
                "error": f"{type(exc).__name__}: {exc}",
                "evidence_source": EVIDENCE_SOURCE,
            }

    return cycle


def aggregate_strategy_evaluation(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """実測値から Strategy 別集計（評価は evidence_count ベース）。"""
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    baseline_failures = 0

    for cycle in cycles:
        if cycle.get("baseline", {}).get("failure_reproduced"):
            baseline_failures += 1
        for name, metrics in (cycle.get("strategies") or {}).items():
            by_strategy.setdefault(name, []).append(metrics)

    summary: dict[str, Any] = {
        "cycles": len(cycles),
        "baseline_failure_reproduced_count": baseline_failures,
        "baseline_failure_not_reproduced_count": len(cycles) - baseline_failures,
        "by_strategy": {},
    }

    for strategy, rows in sorted(by_strategy.items()):
        n = len(rows)
        tc_ok = sum(1 for r in rows if r.get("tool_call_recovery") == "SUCCESS")
        te_ok = sum(1 for r in rows if r.get("tool_execution_success") is True)
        timeouts = sum(1 for r in rows if r.get("timeout"))
        latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
        vram_before = [r["vram_free_before_mib"] for r in rows if r.get("vram_free_before_mib") is not None]
        avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else None
        avg_vram = round(sum(vram_before) / len(vram_before), 1) if vram_before else None

        summary["by_strategy"][strategy] = {
            "evidence_count": n,
            "tool_call_success_count": tc_ok,
            "tool_call_success_rate": round(tc_ok / n, 4) if n else None,
            "tool_execution_success_count": te_ok,
            "timeout_count": timeouts,
            "avg_latency_ms": avg_lat,
            "avg_vram_free_before_mib": avg_vram,
            "evaluation": _strategy_evaluation(n, tc_ok, timeouts, avg_lat, avg_vram),
        }

    summary["most_promising_by_tool_call_rate"] = _most_promising(summary["by_strategy"])
    summary["failure_condition_hints"] = _failure_hints(cycles, summary["by_strategy"])
    return summary


def _strategy_evaluation(n, tc_ok, timeouts, avg_lat, avg_vram) -> dict[str, Any]:
    """実測から導ける範囲のみ記述。過剰評価しない。"""
    if n == 0:
        return {"effectiveness": "NOT_OBSERVED", "reliability": "NOT_OBSERVED", "note": "no data"}
    rate = tc_ok / n if n else 0
    eff = "NOT_DETERMINED"
    if n >= 3 and rate >= 0.67:
        eff = "observed_improvement"
    elif n >= 1 and rate == 0:
        eff = "observed_no_improvement"
    elif n < 3:
        eff = "insufficient_data"
    return {
        "effectiveness": eff,
        "latency_cost": avg_lat,
        "gpu_cost": avg_vram,
        "reliability": "insufficient_data" if n < 3 else ("stable" if timeouts == 0 else "timeout_observed"),
        "applicability": "NOT_DETERMINED",
        "evidence_count": n,
    }


def _most_promising(by_strategy: dict[str, Any]) -> str | None:
    best = None
    best_rate = -1.0
    for name, data in by_strategy.items():
        rate = data.get("tool_call_success_rate")
        if rate is not None and rate > best_rate and (data.get("evidence_count") or 0) >= 1:
            best_rate = rate
            best = name
    return best


def _failure_hints(cycles: list[dict[str, Any]], by_strategy: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    if not cycles:
        return hints
    bf = sum(1 for c in cycles if c.get("baseline", {}).get("failure_reproduced"))
    if bf == 0:
        hints.append("Live baseline failure not reproduced in this session")
    reduce = by_strategy.get("reduce_tool_result") or {}
    inc = by_strategy.get("increase_context") or {}
    if (reduce.get("tool_call_success_rate") or 0) > (inc.get("tool_call_success_rate") or 0):
        hints.append(
            "reduce_tool_result showed equal or better tool_call_success_rate than increase_context in this session"
        )
    if bf > 0 and (by_strategy.get("retry_same_context", {}).get("tool_call_success_count") or 0) > 0:
        hints.append(
            "retry_same_context succeeded at least once: failure may include non-deterministic output variance"
        )
    return hints


def run_compare_batch(
    *,
    runs: int = 1,
    chat_fn: Callable[..., Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    ensure_monitor_dir()
    profile = get_llm_profile()
    ts = _utc_stamp()
    out_dir = output_dir or (HARNESS_RUNS_DIR / f"{ts}_recovery_strategy_compare_p211")
    out_dir.mkdir(parents=True, exist_ok=True)

    search_payload = search_files("read_file", path=".")
    cycles: list[dict[str, Any]] = []
    for i in range(1, runs + 1):
        print(f"[P2-11 compare] cycle {i}/{runs}...", flush=True)
        cycles.append(run_compare_cycle(scenario_id=f"p211_compare_{i}", search_payload=search_payload, chat_fn=chat_fn))

    evaluation = aggregate_strategy_evaluation(cycles)
    report = {
        "task_id": TASK_ID,
        "timestamp": ts,
        "model": profile.get("model"),
        "configured_context": get_configured_context(profile),
        "automatic_recovery_enabled": False,
        "scenario": "search_files_large_result_post_search_read_file",
        "runs_requested": runs,
        "runs_completed": len(cycles),
        "shared_search_payload": payload_metrics(search_payload),
        "cycles": cycles,
        "evaluation": evaluation,
        "evidence_source": EVIDENCE_SOURCE,
        "synthetic_vs_live": "live_llm_experiment",
    }
    out_path = out_dir / "compare.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["output_path"] = str(out_path)
    return report
