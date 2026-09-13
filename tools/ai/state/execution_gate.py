"""
Phase B/C: Compatibility と Safety を独立に扱う ExecutionGate。

Phase C: LLM 分析は直接 Gate を変更しない。
機械が定義した条件を満たすときだけ、machine unknown を
ExperimentCandidate まで検討する（Execute には絶対にしない）。
"""

from __future__ import annotations

from typing import Any

from tools.ai.state.compatibility import (
    COMPAT_CONFIRMED,
    COMPAT_INCOMPATIBLE,
    COMPAT_LIKELY,
    COMPAT_UNKNOWN,
)
from tools.ai.state.llm_safety_analysis import llm_permits_experiment_candidate
from tools.ai.state.safety_assessment import (
    DANGEROUS,
    RISKY,
    SAFE,
    SIDE_READ,
    UNKNOWN,
)

GATE_EXECUTE = "Execute"
GATE_EXPERIMENT = "Experiment"
GATE_EXPERIMENT_CANDIDATE = "ExperimentCandidate"
GATE_BLOCK = "Block"


def _is_limited_readonly_experiment(safety: dict | None) -> bool:
    safety = safety or {}
    effects = list(safety.get("side_effects") or [])
    network = str(safety.get("network_access") or UNKNOWN)
    return effects == [SIDE_READ] and network == "none"


def decide_execution_gate(
    compatibility: dict | None,
    safety: dict | None,
    llm_bundle: dict | None = None,
) -> dict[str, Any]:
    """
    単一スコアに統合しない。両軸をログに残す。
    LLM の「safe」では machine_assessed も decision も直接書き換えない。
    """
    compat_status = str((compatibility or {}).get("status") or COMPAT_UNKNOWN)
    safety_status = str((safety or {}).get("status") or UNKNOWN)
    machine_safety = str(
        (safety or {}).get("machine_assessed") or safety_status
    )
    limited = _is_limited_readonly_experiment(safety)

    decision = GATE_BLOCK
    rationale = []
    llm_experiment_ok = False
    llm_codes: list[str] = []
    machine_not_loosened_by_llm = True

    if compat_status == COMPAT_INCOMPATIBLE:
        decision = GATE_BLOCK
        rationale.append("block_incompatible")
    elif machine_safety == DANGEROUS or safety_status == DANGEROUS:
        decision = GATE_BLOCK
        rationale.append("block_dangerous")
        # LLM が何と言っても緩和しない
        if llm_bundle and (llm_bundle.get("analysis") or {}).get("read_only_likely"):
            rationale.append("llm_safe_ignored_for_machine_dangerous")
            machine_not_loosened_by_llm = True
    elif machine_safety == RISKY or safety_status == RISKY:
        decision = GATE_BLOCK
        rationale.append("block_risky")
        if llm_bundle and (llm_bundle.get("analysis") or {}).get("read_only_likely"):
            rationale.append("llm_safe_ignored_for_machine_risky")
            machine_not_loosened_by_llm = True
    elif machine_safety == UNKNOWN or safety_status == UNKNOWN:
        # Phase C: 明示条件を満たすときのみ ExperimentCandidate（Execute 不可）
        llm_experiment_ok, llm_codes = llm_permits_experiment_candidate(llm_bundle)
        rationale.extend(llm_codes)
        if (
            llm_experiment_ok
            and compat_status != COMPAT_INCOMPATIBLE
            and machine_safety == UNKNOWN
        ):
            decision = GATE_EXPERIMENT_CANDIDATE
            rationale.append("phase_c_experiment_candidate_machine_unknown_llm_ok")
            rationale.append("phase_c_never_promote_to_execute")
            rationale.append("cannot_rule_out_empty_is_not_safety_proof")
            # 提示用。自動実行は allow_execute=False 側で担保する。
            limited = True
        else:
            decision = GATE_BLOCK
            rationale.append("block_safety_unknown")
            if llm_bundle and not llm_bundle.get("ok"):
                rationale.append("block_llm_analysis_failed")
    elif machine_safety == SAFE or safety_status == SAFE:
        if not limited:
            decision = GATE_BLOCK
            rationale.append("block_safe_but_not_limited_experiment_profile")
        elif compat_status == COMPAT_CONFIRMED:
            decision = GATE_EXECUTE
            rationale.append("execute_confirmed_safe")
        elif compat_status == COMPAT_LIKELY:
            decision = GATE_EXPERIMENT
            rationale.append("experiment_likely_safe")
        elif compat_status == COMPAT_UNKNOWN:
            decision = GATE_EXPERIMENT_CANDIDATE
            rationale.append("experiment_candidate_unknown_compat_safe")
        else:
            decision = GATE_BLOCK
            rationale.append("block_unexpected_compat_status")
    else:
        decision = GATE_BLOCK
        rationale.append("block_default")

    # 監査: LLM 経路から Execute への昇格は絶対禁止
    if machine_safety != SAFE and decision == GATE_EXECUTE:
        decision = GATE_BLOCK
        rationale.append("block_prevent_execute_without_machine_safe")
        machine_not_loosened_by_llm = True

    # ExperimentCandidate は「提示のみ」。自動実行しない。
    # Execute / Experiment（machine safe 経路）のみ allow_execute=True。
    allow_execute = decision in (GATE_EXECUTE, GATE_EXPERIMENT)
    presentation_only = decision == GATE_EXPERIMENT_CANDIDATE
    if presentation_only:
        rationale.append("experiment_candidate_presentation_only_no_auto_run")

    return {
        "decision": decision,
        "allow_execute": allow_execute,
        "presentation_only": presentation_only,
        "compatibility_status": compat_status,
        "safety_status": safety_status,
        "machine_safety_status": machine_safety,
        "human_decision": (safety or {}).get("human_decision"),
        "limited_readonly_experiment": limited,
        "rationale_codes": rationale,
        "compatibility": compatibility,
        "safety": safety,
        "llm_experiment_candidate_ok": llm_experiment_ok,
        "machine_not_loosened_by_llm": machine_not_loosened_by_llm,
        "phase": "kss-phase-c" if llm_bundle is not None else "kss-phase-b",
    }


def build_unknown_safety_handoff(
    *,
    purpose: str,
    candidate: dict | None,
    compatibility: dict | None,
    safety: dict | None,
    gate: dict | None,
    alternatives: list | None = None,
    safety_report: dict | None = None,
) -> dict[str, Any]:
    """
    Safety unknown 時に人間へ渡す説明データ（承認を安全根拠にしない）。
    """
    candidate = candidate or {}
    safety = safety or {}
    report = safety_report or {}
    return {
        "kind": "safety_unknown_handoff",
        "purpose": purpose,
        "command": candidate.get("command"),
        "args": list(candidate.get("args") or []),
        "read_targets": _infer_read_targets(candidate),
        "writes": bool(
            {"filesystem_write", "filesystem_delete"}
            & set(safety.get("side_effects") or [])
        ),
        "network": safety.get("network_access"),
        "process_ops": "process_control" in (safety.get("side_effects") or []),
        "required_privilege": safety.get("privilege"),
        "confirmed_safe_elements": [
            c
            for c in (safety.get("rationale_codes") or [])
            if c.startswith("matched_readonly") or c.startswith("wmic_readonly")
        ],
        "unconfirmed_items": list(report.get("unknowns") or [])
        or [
            c
            for c in (safety.get("rationale_codes") or [])
            if any(
                key in c
                for key in ("unknown", "unparsed", "unapproved", "compound")
            )
        ],
        "assumed_risks": safety.get("side_effects") or [],
        "alternatives": alternatives or [],
        "machine_assessed": safety.get("machine_assessed") or safety.get("status"),
        "human_decision": None,
        "compatibility": compatibility,
        "gate": gate,
        "safety_report_ja": report.get("report_text_ja"),
        "why_blocked_ja": (
            f"Gate={gate.get('decision') if gate else 'Block'}。"
            f"機械判定={safety.get('machine_assessed')}。"
            "詳細は Safety Report を参照してください。"
        ),
        "what_to_check_next_ja": list(report.get("next_checks") or []),
        "next_actions": [
            "deeper_static_analysis",
            "additional_web_research",
            "regenerate_simpler_readonly_candidate",
            "human_review_with_structured_handoff",
        ],
        "note": (
            "machine_assessed が unknown のままです。"
            "人間承認があっても machine_assessed は safe に変更しません。"
        ),
    }


def _infer_read_targets(candidate: dict) -> list[str]:
    blob = " ".join(
        [
            str(candidate.get("command") or ""),
            " ".join(str(a) for a in (candidate.get("args") or [])),
        ]
    )
    targets = []
    for marker in (
        "Win32_OperatingSystem",
        "Win32_Processor",
        "Win32_LogicalDisk",
        "Get-Volume",
        "Get-Counter",
        "Get-CimInstance",
        "memory",
        "disk",
        "cpu",
        "gpu",
    ):
        if marker.lower() in blob.lower():
            targets.append(marker)
    return targets


def suggest_followup_after_block(
    gate: dict | None, candidate: dict | None = None
) -> dict[str, Any]:
    """unknown/block 時の協力的フォローアップ提案（progress は変更しない）。"""
    gate = gate or {}
    reasons = list(gate.get("rationale_codes") or [])
    actions = []
    if "block_safety_unknown" in reasons or "block_llm_analysis_failed" in reasons:
        actions.extend(
            [
                "additional_static_analysis",
                "search_for_simpler_readonly_method",
                "ask_candidate_regeneration_readonly",
            ]
        )
    if "block_incompatible" in reasons:
        actions.extend(
            [
                "search_host_os_native_alternative",
                "drop_candidate",
            ]
        )
    if "block_dangerous" in reasons or "block_risky" in reasons:
        actions.extend(
            [
                "reject_candidate",
                "search_readonly_alternative",
            ]
        )
    return {
        "blocked": True,
        "gate_decision": gate.get("decision"),
        "suggested_actions": actions or ["record_and_continue_research"],
        "candidate_command": (candidate or {}).get("command"),
        "explanation_ja": (
            "自動実行は許可されていません。"
            "理由コード: " + ", ".join(reasons or ["unknown"])
        ),
    }
