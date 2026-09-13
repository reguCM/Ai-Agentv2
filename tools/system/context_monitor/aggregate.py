"""Context Monitor 集計（評価はここで後計算）。"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from tools.system.context_monitor.paths import POLICY_JSON, SUMMARY_JSON, ensure_monitor_dir
from tools.system.context_monitor.record import load_observations
from tools.system.context_monitor.schema import EVALUATION_STATES


def _safe_mean(values: list[float | int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _vram_free_mib(gpu: dict[str, Any] | None) -> int | None:
    if not gpu:
        return None
    if "vram_free_mib" in gpu:
        return gpu.get("vram_free_mib")
    status = gpu.get("gpu_status") or gpu
    used = status.get("vram_used") or status.get("vram_used_mib")
    total = status.get("vram_total") or status.get("vram_total_mib")
    if isinstance(used, (int, float)) and isinstance(total, (int, float)):
        return int(total - used)
    return None


def _bucket_context(ctx: Any) -> str:
    if ctx is None:
        return "unknown"
    return str(int(ctx))


def _evaluation_state(total: int, policy: dict[str, Any]) -> str:
    ev = policy.get("evaluation_state") or {}
    if total <= ev.get("insufficient_data_max", 9):
        return "insufficient_data"
    if total <= ev.get("accumulating_max", 19):
        return "accumulating"
    return "ready_for_review"


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    successes = sum(1 for r in rows if (r.get("outcome") or {}).get("success"))
    timeouts = sum(1 for r in rows if (r.get("outcome") or {}).get("timeout"))
    native_tc = sum(1 for r in rows if (r.get("outcome") or {}).get("native_tool_call"))
    elapsed = [
        (r.get("performance") or {}).get("elapsed_ms")
        for r in rows
        if (r.get("performance") or {}).get("elapsed_ms") is not None
    ]
    vram_before = [
        _vram_free_mib(r.get("gpu_before"))
        for r in rows
        if _vram_free_mib(r.get("gpu_before")) is not None
    ]
    vram_after = [
        _vram_free_mib(r.get("gpu_after"))
        for r in rows
        if _vram_free_mib(r.get("gpu_after")) is not None
    ]
    return {
        "observation_count": n,
        "success_count": successes,
        "failure_count": n - successes,
        "success_rate": round(successes / n, 4) if n else None,
        "timeout_count": timeouts,
        "timeout_rate": round(timeouts / n, 4) if n else None,
        "native_tool_call_count": native_tc,
        "native_tool_call_rate": round(native_tc / n, 4) if n else None,
        "avg_elapsed_ms": round(_safe_mean(elapsed), 1) if elapsed else None,
        "avg_vram_free_before_mib": round(_safe_mean(vram_before), 1) if vram_before else None,
        "avg_vram_free_after_mib": round(_safe_mean(vram_after), 1) if vram_after else None,
    }


def aggregate_observations(
    observations: list[dict[str, Any]] | None = None,
    *,
    policy_path=None,
) -> dict[str, Any]:
    """観測データを集計。事実（observations）と評価（summary）を分離した出力。"""
    rows = observations if observations is not None else load_observations()
    policy_file = policy_path or POLICY_JSON
    with open(policy_file, encoding="utf-8") as f:
        policy = json.load(f)

    by_context: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_context_task: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        ctx = _bucket_context((row.get("execution") or {}).get("context_size"))
        task = (row.get("execution") or {}).get("task_type") or "unknown"
        by_context[ctx].append(row)
        by_task[task].append(row)
        by_context_task[f"{ctx}:{task}"].append(row)

    global_metrics = _aggregate_group(rows)
    eval_state = _evaluation_state(len(rows), policy)

    context_summary = {
        ctx: {
            **_aggregate_group(group),
            "evaluation_state": _evaluation_state(len(group), policy),
        }
        for ctx, group in sorted(by_context.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
    }

    task_summary = {
        task: _aggregate_group(group) for task, group in sorted(by_task.items())
    }

    # GPU クロス分析用（Context × 実行前 VRAM 空き）
    cross_vram_elapsed: list[dict[str, Any]] = []
    for row in rows:
        ctx = _bucket_context((row.get("execution") or {}).get("context_size"))
        vram_free = _vram_free_mib(row.get("gpu_before"))
        elapsed = (row.get("performance") or {}).get("elapsed_ms")
        if vram_free is not None:
            cross_vram_elapsed.append(
                {
                    "context_size": int(ctx) if ctx.isdigit() else ctx,
                    "vram_free_before_mib": vram_free,
                    "elapsed_ms": elapsed,
                    "timeout": (row.get("outcome") or {}).get("timeout"),
                    "success": (row.get("outcome") or {}).get("success"),
                }
            )

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_observations": len(rows),
        "evaluation_state": eval_state,
        "evaluation_state_label": {
            "insufficient_data": "データ不足（断定不可）",
            "accumulating": "データ蓄積中",
            "ready_for_review": "レビュー可能なデータ量",
        }.get(eval_state, eval_state),
        "global_metrics": global_metrics,
        "by_context_size": context_summary,
        "by_task_type": task_summary,
        "cross_analysis": {
            "context_x_vram_free_before": cross_vram_elapsed,
        },
        "policy_version": policy.get("version"),
        "note": "評価は集計時に再計算。観測 JSONL は変更しない。",
    }
    return summary


def write_summary(*, path=None) -> dict[str, Any]:
    ensure_monitor_dir()
    summary = aggregate_observations()
    target = path or SUMMARY_JSON
    with open(target, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary
