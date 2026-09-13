"""Recovery 候補の人間向けサマリ・経験記録。"""
from __future__ import annotations

import json
from typing import Any

from tools.system.context_monitor.paths import RECOVERY_EXPERIENCE_JSONL, ensure_monitor_dir


def format_recovery_approval_summary(decision: dict[str, Any]) -> str:
    """CLI 承認用テキスト。"""
    lines = [
        "=== Recovery 候補 ===",
        f"原因候補: {decision.get('failure_type')}",
        f"現在 Context: {decision.get('current_context')} (configured: {decision.get('configured_context')})",
        f"提案 Strategy: {decision.get('candidate_strategy')}",
        f"提案 Context: {decision.get('candidate_context')}",
        f"信頼度: {decision.get('confidence')}",
        "",
        "根拠:",
    ]
    for r in decision.get("reason") or []:
        lines.append(f"  - {r}")
    evidence = decision.get("evidence") or {}
    if evidence:
        lines.append("")
        lines.append("Evidence:")
        for k in (
            "evidence_source",
            "current_context_observations",
            "candidate_context_observations",
            "candidate_native_tool_call_rate",
            "historical_improvement_observed",
        ):
            if k in evidence:
                lines.append(f"  {k}: {evidence[k]}")
    gpu = decision.get("gpu_state") or {}
    lines.extend(
        [
            "",
            "GPU:",
            f"  vram_free_mib: {gpu.get('vram_free_mib')}",
            f"  vram_total_mib: {gpu.get('vram_total_mib')}",
            f"  execution_allowed: {decision.get('execution_allowed')}",
            "",
            "実行: 明示承認が必要 (automatic_execution_allowed="
            f"{decision.get('automatic_execution_allowed')})",
        ]
    )
    return "\n".join(lines)


def format_recommendation_list(recommendation: dict[str, Any]) -> str:
    """順位付き Recovery 候補リスト（Agent/CLI 用）。"""
    lines = ["=== Recovery Candidates (ranked) ==="]
    situation = recommendation.get("situation") or {}
    lines.append(f"Failure: {situation.get('failure_type')}")
    lines.append(
        f"Tool Result: count={situation.get('tool_result_count')} "
        f"bytes={situation.get('payload_bytes')} truncated={situation.get('truncated')}"
    )
    lines.append(f"Context: configured={situation.get('configured_context')}")
    lines.append("")
    for item in recommendation.get("recommendation_summary") or []:
        lines.append(
            f"{item.get('rank')}. {item.get('strategy')} "
            f"(score={item.get('rank_score')}, confidence={item.get('confidence')}, "
            f"evidence={item.get('evidence_count')})"
        )
        for r in item.get("reasons") or []:
            lines.append(f"     - {r}")
        lines.append("")
    ctx = recommendation.get("context_expansion") or {}
    if ctx:
        lines.append(
            f"Context Expansion (increase_context): gate={ctx.get('gate_status')} "
            f"[last-resort, not in normal ranking]"
        )
        for r in ctx.get("blocked_reasons") or []:
            lines.append(f"  blocked: {r}")
        lines.append("")
    lines.append("実行: 明示承認が必要 (automatic_recovery=OFF)")
    return "\n".join(lines)


def evaluate_tool_call_recovery(
    *,
    native_tool_call: bool,
    native_tool_names: list[str] | None,
    expected_tool: str | None,
    tool_execution_ok: bool | None,
    timeout: bool,
    execution_result: str,
) -> dict[str, str]:
    """tool_call_recovery / task_result / execution_result を分離。"""
    names = native_tool_names or []
    expected = expected_tool or "read_file"
    tool_generated = expected in names if expected else bool(names)

    if timeout and tool_generated:
        tcr = "PARTIAL"
    elif timeout:
        tcr = "FAILURE"
    elif tool_generated and tool_execution_ok is False:
        tcr = "PARTIAL"
    elif tool_generated and (tool_execution_ok is True or tool_execution_ok is None):
        tcr = "SUCCESS"
    elif execution_result == "success" and tool_generated:
        tcr = "SUCCESS"
    else:
        tcr = "FAILURE"

    if tcr == "SUCCESS" and tool_execution_ok is False:
        task = "FAILURE"
    elif timeout:
        task = "UNKNOWN"
    elif tcr == "SUCCESS":
        task = "UNKNOWN"
    else:
        task = "FAILURE"

    exec_res = execution_result
    if timeout and tcr == "PARTIAL":
        exec_res = "partial"

    return {
        "tool_call_recovery": tcr,
        "task_result": task,
        "execution_result": exec_res,
    }


def append_recovery_experience(record: dict[str, Any], *, path=None) -> str:
    ensure_monitor_dir()
    target = path or RECOVERY_EXPERIENCE_JSONL
    exp_id = record.get("experience_id") or record.get("recovery_id") or ""
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(exp_id)


def tag_evidence_source(evidence: dict[str, Any], source: str) -> dict[str, Any]:
    tagged = dict(evidence)
    tagged["evidence_source"] = source
    return tagged
