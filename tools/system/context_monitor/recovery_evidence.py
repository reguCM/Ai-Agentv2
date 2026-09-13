"""Recovery Strategy Evidence 蓄積・読込（P2-11 等）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from tools.system.context_monitor.paths import MONITOR_DIR, ensure_monitor_dir

STRATEGY_EVIDENCE_JSONL = MONITOR_DIR / "strategy_evidence.jsonl"
P11_COMPARE_GLOB = "*_recovery_strategy_compare_p211/compare.json"

EvidencePolarity = Literal["positive", "negative", "neutral"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def classify_evidence_polarity(record: dict[str, Any]) -> EvidencePolarity:
    """
    Strategy 実行結果から Positive / Negative Evidence を判定。
    recovery_result / tool_call_success / timeout から導出（Strategy 自体とは分離）。
    """
    if record.get("evidence_polarity") in ("positive", "negative", "neutral"):
        return record["evidence_polarity"]

    recovery_result = record.get("recovery_result")
    if recovery_result == "success":
        return "positive"
    if recovery_result == "failure":
        return "negative"

    tc = record.get("tool_call_success")
    if tc is True:
        return "positive"
    if tc is False and record.get("timeout"):
        return "negative"
    if tc is False:
        return "negative"
    if record.get("timeout"):
        return "negative"
    return "neutral"


def append_strategy_evidence(record: dict[str, Any], *, path: Path | None = None) -> None:
    ensure_monitor_dir()
    target = path or STRATEGY_EVIDENCE_JSONL
    row = dict(record)
    row.setdefault("evidence_polarity", classify_evidence_polarity(row))
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_strategy_evidence_record(
    *,
    strategy: str,
    failure_type: str | None = None,
    configured_context: int | None = None,
    runtime_context: int | None = None,
    tool_result_count: int | None = None,
    payload_bytes: int | None = None,
    truncated: bool | None = None,
    tool_call_success: bool | None = None,
    tool_execution_success: bool | None = None,
    timeout: bool | None = None,
    latency_ms: int | float | None = None,
    gpu_before: dict[str, Any] | None = None,
    gpu_after: dict[str, Any] | None = None,
    recovery_result: str | None = None,
    scenario_id: str | None = None,
    evidence_source: str | None = None,
    phase: str = "recovery",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """通常の開発・テスト・実ケースから Evidence を記録するための正規化レコード。"""
    record: dict[str, Any] = {
        "strategy": strategy,
        "failure_type": failure_type,
        "configured_context": configured_context,
        "runtime_context": runtime_context,
        "tool_result_count": tool_result_count,
        "payload_bytes": payload_bytes,
        "truncated": truncated,
        "tool_call_success": tool_call_success,
        "tool_execution_success": tool_execution_success,
        "timeout": timeout,
        "latency_ms": latency_ms,
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "recovery_result": recovery_result,
        "scenario_id": scenario_id,
        "evidence_source": evidence_source,
        "phase": phase,
    }
    if extra:
        record.update(extra)
    record["evidence_polarity"] = classify_evidence_polarity(record)
    return record


def record_strategy_outcome(
    *,
    strategy: str,
    failure_type: str | None = None,
    configured_context: int | None = None,
    runtime_context: int | None = None,
    tool_result_count: int | None = None,
    payload_bytes: int | None = None,
    truncated: bool | None = None,
    tool_call_success: bool | None = None,
    tool_execution_success: bool | None = None,
    timeout: bool | None = None,
    latency_ms: int | float | None = None,
    gpu_before: dict[str, Any] | None = None,
    gpu_after: dict[str, Any] | None = None,
    recovery_result: str | None = None,
    scenario_id: str | None = None,
    evidence_source: str | None = None,
    phase: str = "recovery",
    extra: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Strategy 実行結果を Evidence として保存（今後の実ケース蓄積用）。"""
    record = build_strategy_evidence_record(
        strategy=strategy,
        failure_type=failure_type,
        configured_context=configured_context,
        runtime_context=runtime_context,
        tool_result_count=tool_result_count,
        payload_bytes=payload_bytes,
        truncated=truncated,
        tool_call_success=tool_call_success,
        tool_execution_success=tool_execution_success,
        timeout=timeout,
        latency_ms=latency_ms,
        gpu_before=gpu_before,
        gpu_after=gpu_after,
        recovery_result=recovery_result,
        scenario_id=scenario_id,
        evidence_source=evidence_source,
        phase=phase,
        extra=extra,
    )
    append_strategy_evidence(record, path=path)
    return record


def load_strategy_evidence(*, path: Path | None = None) -> list[dict[str, Any]]:
    target = path or STRATEGY_EVIDENCE_JSONL
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def import_p11_compare_evidence(
    compare_path: Path | None = None,
    *,
    skip_if_imported: bool = True,
) -> dict[str, Any]:
    """P2-11 compare.json を strategy_evidence.jsonl に取り込む（元ファイル不変）。"""
    ensure_monitor_dir()
    if compare_path is None:
        matches = sorted(_repo_root().joinpath("runs", "ai_tool").glob(P11_COMPARE_GLOB))
        compare_path = matches[-1] if matches else None
    if compare_path is None or not compare_path.exists():
        return {"imported": 0, "status": "NOT_FOUND"}

    source_ref = str(compare_path.relative_to(_repo_root())).replace("\\", "/")
    existing = load_strategy_evidence()
    if skip_if_imported and any(r.get("source_ref") == source_ref for r in existing):
        return {"imported": 0, "status": "already_imported", "source_ref": source_ref}

    with open(compare_path, encoding="utf-8") as f:
        report = json.load(f)

    imported = 0
    shared = report.get("shared_search_payload") or {}
    for cycle in report.get("cycles") or []:
        baseline = cycle.get("baseline") or {}
        base_record = {
            "source": "p2-11_live_strategy_compare",
            "source_ref": source_ref,
            "task_id": report.get("task_id"),
            "scenario_id": cycle.get("scenario_id"),
            "failure_type": baseline.get("failure_type"),
            "configured_context": cycle.get("configured_context"),
            "runtime_context": baseline.get("context"),
            "tool_result_count": baseline.get("result_count") or shared.get("result_count"),
            "payload_bytes": baseline.get("payload_bytes") or shared.get("payload_bytes"),
            "truncated": baseline.get("truncated") if baseline.get("truncated") is not None else shared.get("truncated"),
            "phase": "baseline",
        }
        append_strategy_evidence(
            {
                **base_record,
                "strategy": "baseline",
                "tool_call_success": baseline.get("tool_call_recovery") == "SUCCESS",
                "tool_execution_success": baseline.get("tool_execution_success"),
                "timeout": baseline.get("timeout"),
                "latency_ms": baseline.get("latency_ms"),
                "recovery_result": "failure",
            }
        )
        imported += 1

        for strategy, metrics in (cycle.get("strategies") or {}).items():
            if metrics.get("error"):
                continue
            append_strategy_evidence(
                {
                    **base_record,
                    "phase": "recovery",
                    "strategy": strategy,
                    "runtime_context": metrics.get("context") or metrics.get("runtime_context"),
                    "tool_call_success": metrics.get("tool_call_recovery") == "SUCCESS",
                    "tool_execution_success": metrics.get("tool_execution_success"),
                    "timeout": metrics.get("timeout"),
                    "latency_ms": metrics.get("latency_ms"),
                    "recovery_result": (
                        "success" if metrics.get("tool_call_recovery") == "SUCCESS" else "failure"
                    ),
                    "gpu_vram_free_before_mib": metrics.get("vram_free_before_mib"),
                }
            )
            imported += 1

    return {"imported": imported, "status": "imported", "source_ref": source_ref}


def query_strategy_evidence(
    evidence: list[dict[str, Any]] | None = None,
    *,
    strategy: str | None = None,
    failure_type: str | None = None,
    min_match_count: int | None = None,
    truncated: bool | None = None,
) -> list[dict[str, Any]]:
    rows = evidence if evidence is not None else load_strategy_evidence()
    out: list[dict[str, Any]] = []
    for row in rows:
        if strategy and row.get("strategy") != strategy:
            continue
        if failure_type and row.get("failure_type") != failure_type:
            continue
        if min_match_count is not None:
            rc = row.get("tool_result_count")
            if rc is None or int(rc) < min_match_count:
                continue
        if truncated is not None and row.get("truncated") is not truncated:
            continue
        out.append(row)
    return out


def summarize_strategy_evidence(
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Strategy 別の実測サマリ（事実のみ）。"""
    rows = evidence if evidence is not None else load_strategy_evidence()
    recovery_rows = [r for r in rows if r.get("phase") == "recovery" and r.get("strategy")]
    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in recovery_rows:
        by_strategy.setdefault(str(row["strategy"]), []).append(row)

    summary: dict[str, dict[str, Any]] = {}
    for strategy, group in by_strategy.items():
        n = len(group)
        tc_ok = sum(1 for r in group if r.get("tool_call_success"))
        timeouts = sum(1 for r in group if r.get("timeout"))
        latencies = [r["latency_ms"] for r in group if r.get("latency_ms") is not None]
        positive = sum(1 for r in group if r.get("evidence_polarity") == "positive")
        negative = sum(1 for r in group if r.get("evidence_polarity") == "negative")
        summary[strategy] = {
            "evidence_count": n,
            "positive_evidence_count": positive,
            "negative_evidence_count": negative,
            "tool_call_success_count": tc_ok,
            "tool_call_success_rate": round(tc_ok / n, 4) if n else None,
            "timeout_count": timeouts,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        }
    return summary
