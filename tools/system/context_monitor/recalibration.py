"""再調整要求（RECALIBRATION）判定。自動 Context 変更は行わない。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from tools.system.context_monitor.aggregate import aggregate_observations
from tools.system.context_monitor.paths import POLICY_JSON, RECALIBRATION_JSON, ensure_monitor_dir


def _load_policy(path=None) -> dict[str, Any]:
    with open(path or POLICY_JSON, encoding="utf-8") as f:
        return json.load(f)


def _metric_value(metric: str, metrics: dict[str, Any], baseline: dict[str, Any] | None) -> float | None:
    if metric in metrics and metrics[metric] is not None:
        return float(metrics[metric])
    if baseline and metric in baseline:
        return float(baseline[metric])
    return None


def evaluate_recalibration(
    summary: dict[str, Any] | None = None,
    *,
    policy: dict[str, Any] | None = None,
    focus_context: int | None = None,
) -> dict[str, Any]:
    """再調整要求候補を判定。status と reason を返す。"""
    policy = policy or _load_policy()
    summary = summary or aggregate_observations()

    ctx_key = str(focus_context) if focus_context is not None else None
    if ctx_key and ctx_key in summary.get("by_context_size", {}):
        metrics = summary["by_context_size"][ctx_key]
        scope = f"context={ctx_key}"
    else:
        metrics = summary.get("global_metrics") or {}
        scope = "global"
        ctx_key = None

    n = metrics.get("observation_count") or 0
    baseline = summary.get("global_metrics") or {}
    triggered: list[dict[str, Any]] = []

    for rule in policy.get("recalibration_rules") or []:
        if not rule.get("enabled", True):
            continue
        rid = rule.get("id", "unknown")
        rtype = rule.get("type")
        min_obs = rule.get("min_observations", 0)
        if n < min_obs and rtype != "manual_flag":
            continue

        if rtype == "manual_flag":
            continue

        metric_name = rule.get("metric", "")
        op = rule.get("operator", ">=")
        value = rule.get("value")
        current = _metric_value(metric_name, metrics, baseline)

        fired = False
        detail: dict[str, Any] = {"rule_id": rid, "metric": metric_name, "current": current}

        if current is None:
            detail["skipped"] = "metric_unavailable"
        elif rtype == "baseline_delta":
            base_val = _metric_value(rule.get("baseline_key", ""), baseline, baseline)
            delta_ratio = rule.get("delta_ratio", 0.25)
            detail["baseline"] = base_val
            if base_val is not None and base_val > 0:
                threshold = base_val * (1 + delta_ratio)
                detail["threshold"] = threshold
                fired = current > threshold if op == ">" else current >= threshold
        else:
            detail["threshold"] = value
            if op == ">=":
                fired = current >= float(value)
            elif op == ">":
                fired = current > float(value)
            elif op == "<=":
                fired = current <= float(value)
            elif op == "<":
                fired = current < float(value)

        if fired:
            triggered.append(
                {
                    "rule_id": rid,
                    "description": rule.get("description"),
                    "weight": rule.get("weight", 1),
                    "detail": detail,
                }
            )

    total_weight = sum(t.get("weight", 1) for t in triggered)
    thresh = policy.get("recalibration_recommend_threshold") or {}
    min_rules = thresh.get("min_triggered_rules", 2)
    min_weight = thresh.get("min_total_weight", 3)

    eval_state = summary.get("evaluation_state", "insufficient_data")
    if eval_state == "insufficient_data":
        status = "none"
        message = "データ不足のため再調整要求は生成しません。"
    elif len(triggered) >= min_rules and total_weight >= min_weight:
        status = "recalibration_recommended"
        message = "Context 再調整テストを推奨します（自動変更は行いません）。"
    elif triggered:
        status = "candidate"
        message = "再調整要求候補がありますが、閾値未満です。"
    else:
        status = "none"
        message = "現時点で再調整要求条件は検出されていません。"

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recalibration_required": status == "recalibration_recommended",
        "status": status,
        "scope": scope,
        "focus_context_size": int(ctx_key) if ctx_key and ctx_key.isdigit() else ctx_key,
        "evaluation_state": eval_state,
        "observation_count": n,
        "triggered_rules": triggered,
        "triggered_rule_count": len(triggered),
        "total_weight": total_weight,
        "message": message,
        "reasons": [
            f"{t['rule_id']}: {t.get('description')} ({t.get('detail')})"
            for t in triggered
        ],
        "policy_version": policy.get("version"),
        "note": "RECALIBRATION_REQUIRED は報告のみ。Context の自動変更は行わない。",
    }
    return result


def write_recalibration_status(*, focus_context: int | None = 16384, path=None) -> dict[str, Any]:
    ensure_monitor_dir()
    summary = aggregate_observations()
    status = evaluate_recalibration(summary, focus_context=focus_context)
    target = path or RECALIBRATION_JSON
    with open(target, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    return status
