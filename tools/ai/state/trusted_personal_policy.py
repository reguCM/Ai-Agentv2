"""
Phase D-0: Trusted Personal Policy 骨格。

Execution Gate の直後に置く実行認可レイヤ。
Gate 自体は変更しない。D-0 では AUTO 範囲を拡大しない。

- default mode: Gate 結果を完全 passthrough
- trusted_personal mode: machine safe 経路を不必要に CONFIRM へ落とさない
- resource / reversibility 等は判断材料の枠のみ（閾値なし）
"""

from __future__ import annotations

import os
from typing import Any

from tools.ai.state.safety_assessment import (
    DANGEROUS,
    RISKY,
    SAFE,
    SIDE_FS_DELETE,
    SIDE_FS_WRITE,
    SIDE_NET,
    SIDE_PRIV,
    SIDE_PROCESS,
    SIDE_READ,
    SIDE_SERVICE,
    SIDE_STATE,
    SIDE_UNKNOWN,
    UNKNOWN,
)

MODE_DEFAULT = "default"
MODE_TRUSTED_PERSONAL = "trusted_personal"

POLICY_AUTO = "AUTO"
POLICY_MONITORED = "MONITORED"
POLICY_CONFIRM = "CONFIRM"
POLICY_BLOCK = "BLOCK"

REV_REVERSIBLE = "reversible"
REV_PARTIAL = "partially_reversible"
REV_DIFFICULT = "difficult_to_reverse"
REV_IRREVERSIBLE = "irreversible"
REV_UNKNOWN = "unknown"

IMPACT_SCOPES = (
    "single_path",
    "project",
    "user_profile",
    "system",
    "external_service",
    "unknown",
)
IMPACT_BREADTHS = ("narrow", "wide", "unbounded", "unknown")

EXT_LOCAL_READ = "local_read"
EXT_LOCAL_WRITE = "local_write"
EXT_LOCAL_DELETE = "local_delete"
EXT_PROCESS = "process_control"
EXT_SERVICE = "service_control"
EXT_NET_READ = "network_read"
EXT_NET_WRITE = "network_write"
EXT_EXTERNAL = "external_side_effect"
EXT_PRIV = "privilege_change"
EXT_UNKNOWN = "unknown"

RESOURCE_SAFE = "safe"
RESOURCE_CONSTRAINED = "constrained"
RESOURCE_CRITICAL = "critical"
RESOURCE_UNKNOWN = "unknown"

PHASE = "kss-phase-d0"
PHASE_D1A = "kss-phase-d1a"

# D-0 明示: これらの閾値ルールは存在しない（テストがソースを検証する）
PHASE_D0_EXPLICITLY_ABSENT_RULES = (
    "disk_ten_percent_free_ratio_rule",
    "gpu_utilization_fixed_threshold",
    "cpu_utilization_fixed_threshold",
    "memory_utilization_fixed_threshold",
    "long_running_equals_dangerous",
    "long_running_immediate_block",
)


def resolve_trusted_personal_mode(explicit: str | None = None) -> str:
    if explicit in (MODE_DEFAULT, MODE_TRUSTED_PERSONAL):
        return explicit
    env = str(os.environ.get("AI_AGENT_TRUSTED_PERSONAL_MODE") or "").strip().lower()
    if env in (MODE_DEFAULT, MODE_TRUSTED_PERSONAL):
        return env
    return MODE_DEFAULT


def empty_reversibility(**overrides: Any) -> dict[str, Any]:
    base = {
        "status": REV_UNKNOWN,
        "restore_mechanisms": [],
        "targets_covered": UNKNOWN,
        "uncovered_targets": [],
        "evidence": [],
        "rationale_codes": ["reversibility_not_evaluated_phase_d0"],
        "note": (
            "Git リポジトリの存在だけでは reversible としません。"
            "復元手段とその対象カバレッジを分けて評価します。"
        ),
    }
    base.update(overrides)
    return base


def assess_reversibility_from_facts(facts: dict | None = None) -> dict[str, Any]:
    """
    機械事実からの可逆性骨格。閾値や楽観推定はしない。
    git_repo=True だけでは reversible にしない。
    untracked を restore 可能と誤認しない。
    """
    facts = facts or {}
    codes = ["reversibility_assessed_from_facts"]
    mechanisms = []
    uncovered = []
    evidence = []

    git_repo = facts.get("git_repo")
    if git_repo is True:
        evidence.append("git_repo_present")
        codes.append("git_present_is_not_sufficient_for_reversible")
        # メカニズム候補として列挙はするが、targets_covered なしでは採用しない
        if facts.get("restore_via_git") is True:
            mechanisms.append("git_restore")
    elif git_repo is False:
        evidence.append("not_a_git_repo")
    else:
        evidence.append("git_repo_unknown")
        codes.append("git_repo_unknown")

    tracked = list(facts.get("tracked_targets") or [])
    untracked = list(facts.get("untracked_targets") or [])
    ignored = list(facts.get("ignored_targets") or [])
    outside = list(facts.get("outside_repo_targets") or [])

    for path in untracked:
        uncovered.append({"path": path, "reason": "untracked_not_restorable_via_git"})
        codes.append("untracked_not_treated_as_restorable")
    for path in ignored:
        uncovered.append({"path": path, "reason": "ignored_not_assumed_restorable"})
    for path in outside:
        uncovered.append({"path": path, "reason": "outside_repo"})

    targets_covered = facts.get("targets_covered")
    if targets_covered is None:
        if untracked or ignored or outside:
            targets_covered = False
        elif tracked and mechanisms and facts.get("all_targets_tracked") is True:
            targets_covered = True
        else:
            targets_covered = UNKNOWN

    # reversible 条件: 明示的に targets_covered=True かつ mechanism あり、かつ uncovered なし
    status = REV_UNKNOWN
    if facts.get("force_status") in (
        REV_REVERSIBLE,
        REV_PARTIAL,
        REV_DIFFICULT,
        REV_IRREVERSIBLE,
        REV_UNKNOWN,
    ):
        status = facts["force_status"]
    elif targets_covered is True and mechanisms and not uncovered:
        status = REV_REVERSIBLE
        codes.append("targets_covered_by_restore_mechanism")
    elif mechanisms and uncovered:
        status = REV_PARTIAL
        codes.append("partial_coverage_only")
    elif git_repo is True and targets_covered is not True:
        # Git があるだけでは reversible にしない
        status = REV_UNKNOWN
        codes.append("git_without_target_coverage_remains_unknown")

    return empty_reversibility(
        status=status,
        restore_mechanisms=mechanisms,
        targets_covered=targets_covered
        if targets_covered in (True, False, UNKNOWN)
        else UNKNOWN,
        uncovered_targets=uncovered,
        evidence=evidence,
        rationale_codes=list(dict.fromkeys(codes)),
    )


def empty_impact(**overrides: Any) -> dict[str, Any]:
    base = {
        "scope": "unknown",
        "breadth": "unknown",
        "rationale_codes": ["impact_not_evaluated_phase_d0"],
    }
    base.update(overrides)
    if base["scope"] not in IMPACT_SCOPES:
        base["scope"] = "unknown"
    if base["breadth"] not in IMPACT_BREADTHS:
        base["breadth"] = "unknown"
    return base


def empty_external_effects(**overrides: Any) -> dict[str, Any]:
    base = {
        "effects": [],
        "network_read": UNKNOWN,
        "network_write": UNKNOWN,
        "rationale_codes": ["external_effects_not_evaluated_phase_d0"],
        "mapped_from_machine_side_effects": False,
    }
    base.update(overrides)
    return base


def map_external_effects_from_safety(safety: dict | None) -> dict[str, Any]:
    """
    既存 Safety side_effects を壊さず、Policy 用 external_effects へ写像。
    network_egress → network_write。network_read は別フィールド（未検出は unknown）。
    """
    safety = safety or {}
    sides = [str(x) for x in (safety.get("side_effects") or [])]
    effects = []
    network_read = UNKNOWN
    network_write = UNKNOWN
    codes = ["external_effects_mapped_from_machine_side_effects"]

    for side in sides:
        if side == SIDE_READ:
            effects.append(EXT_LOCAL_READ)
        elif side == SIDE_FS_WRITE:
            effects.append(EXT_LOCAL_WRITE)
        elif side == SIDE_FS_DELETE:
            effects.append(EXT_LOCAL_DELETE)
        elif side == SIDE_PROCESS:
            effects.append(EXT_PROCESS)
        elif side == SIDE_SERVICE:
            effects.append(EXT_SERVICE)
        elif side == SIDE_NET:
            effects.append(EXT_NET_WRITE)
            network_write = True
            codes.append("network_egress_mapped_to_network_write")
        elif side == SIDE_PRIV:
            effects.append(EXT_PRIV)
        elif side == SIDE_STATE:
            effects.append(EXT_EXTERNAL)
        elif side == SIDE_UNKNOWN:
            effects.append(EXT_UNKNOWN)
        else:
            effects.append(EXT_UNKNOWN)
            codes.append(f"unmapped_side_effect:{side}")

    # 明示フィールドがあれば優先（将来の分離検出）
    if "network_read" in safety:
        network_read = safety.get("network_read")
        if network_read is True:
            effects.append(EXT_NET_READ)
    if "network_write" in safety:
        network_write = safety.get("network_write")
        if network_write is True and EXT_NET_WRITE not in effects:
            effects.append(EXT_NET_WRITE)

    net_access = str(safety.get("network_access") or UNKNOWN)
    if net_access == "none":
        if network_write is UNKNOWN:
            network_write = False
        if network_read is UNKNOWN:
            network_read = False
        codes.append("network_access_none_sets_read_write_false")
    elif net_access == "outbound":
        network_write = True
        if EXT_NET_WRITE not in effects:
            effects.append(EXT_NET_WRITE)
        # read は outbound だけでは確定しない
        codes.append("network_access_outbound_implies_write_not_read")

    effects = list(dict.fromkeys(effects))
    return empty_external_effects(
        effects=effects,
        network_read=network_read,
        network_write=network_write,
        rationale_codes=list(dict.fromkeys(codes)),
        mapped_from_machine_side_effects=True,
    )


def empty_execution_runtime(**overrides: Any) -> dict[str, Any]:
    """長時間＝危険とは定義しない。終了性・停止性を分解して保持する。"""
    base = {
        "duration_estimate": UNKNOWN,
        "termination_statically_known": UNKNOWN,
        "infinite_loop_suspected": UNKNOWN,
        "stop_means_available": UNKNOWN,
        "child_process_fanout_risk": UNKNOWN,
        "rationale_codes": [
            "execution_runtime_not_evaluated_phase_d0",
            "long_running_not_defined_as_dangerous",
        ],
        "note": "実行時間が長いこと自体を危険とはみなしません。",
    }
    base.update(overrides)
    return base


def empty_environment_resources(**overrides: Any) -> dict[str, Any]:
    base = {
        "disk_free_bytes": UNKNOWN,
        "disk_free_ratio": UNKNOWN,
        "memory_available_bytes": UNKNOWN,
        "gpu_memory_free_bytes": UNKNOWN,
        "cpu_load": UNKNOWN,
        "gpu_utilization": UNKNOWN,
        "active_processes": UNKNOWN,
        "resource_limits": UNKNOWN,
        "source": "none",
        "rationale_codes": ["environment_resources_not_probed_phase_d0"],
    }
    base.update(overrides)
    return base


def empty_resource_impact(**overrides: Any) -> dict[str, Any]:
    base = {
        "disk_growth": UNKNOWN,
        "memory_consumption": UNKNOWN,
        "gpu_memory_consumption": UNKNOWN,
        "cpu_consumption": UNKNOWN,
        "execution_duration": UNKNOWN,
        "unbounded_execution": UNKNOWN,
        "rationale_codes": ["resource_impact_not_estimated_phase_d0"],
    }
    base.update(overrides)
    return base


def empty_resource_assessment(**overrides: Any) -> dict[str, Any]:
    base = {
        "environment_resources": empty_environment_resources(),
        "resource_impact": empty_resource_impact(),
        "execution_runtime": empty_execution_runtime(),
        "resource_safety": {
            "status": RESOURCE_UNKNOWN,
            "rationale_codes": [
                "resource_not_evaluated_phase_d0",
                "resource_unknown_not_treated_as_safe",
            ],
        },
        "not_merged_into_machine_safety": True,
        "web_content_used": False,
        "llm_final_authority": False,
        "thresholds_applied": False,
        "phase_d0_absent_rules": list(PHASE_D0_EXPLICITLY_ABSENT_RULES),
    }
    base.update(overrides)
    # unknown を safe にしない
    rs = base.get("resource_safety") or {}
    if rs.get("status") == RESOURCE_SAFE and not rs.get("explicitly_evaluated"):
        base["resource_safety"] = {
            **rs,
            "status": RESOURCE_UNKNOWN,
            "rationale_codes": list(rs.get("rationale_codes") or [])
            + ["blocked_implicit_resource_safe"],
        }
    return base


def _machine_status(safety: dict | None) -> str:
    safety = safety or {}
    return str(safety.get("machine_assessed") or safety.get("status") or UNKNOWN)


def _passthrough_decision(gate: dict | None) -> tuple[str, bool, list[str]]:
    gate = gate or {}
    allow = bool(gate.get("allow_execute"))
    decision = str(gate.get("decision") or "Block")
    codes = ["phase_d0_passthrough_gate"]
    if allow:
        return POLICY_AUTO, True, codes + ["passthrough_gate_allow_execute"]
    if decision == "ExperimentCandidate" or gate.get("presentation_only"):
        return (
            POLICY_CONFIRM,
            False,
            codes
            + [
                "passthrough_experiment_candidate_as_confirm_presentation",
                "phase_d0_no_auto_expand",
            ],
        )
    return POLICY_BLOCK, False, codes + ["passthrough_gate_block"]


def evaluate_trusted_personal_policy(
    *,
    mode: str | None = None,
    gate: dict | None = None,
    compatibility: dict | None = None,
    safety: dict | None = None,
    llm_bundle: dict | None = None,
    reversibility: dict | None = None,
    impact: dict | None = None,
    external_effects: dict | None = None,
    resource_assessment: dict | None = None,
    git_facts: dict | None = None,
    web_safety_claims: list | None = None,
    candidate: dict | None = None,
    observation: dict | None = None,
    execution_id: str | None = None,
) -> dict[str, Any]:
    """
    Gate 結果を入力に Policy を返す。Gate / machine_assessed は改変しない。
    D-0/D-1a: AUTO 拡大なし。default は完全 passthrough。
    D-1a の観測結果は判断材料として添付するだけで allow_execute を変えない。
    """
    resolved_mode = resolve_trusted_personal_mode(mode)
    gate = gate or {}
    safety = safety or {}
    llm_bundle = llm_bundle or {}
    machine = _machine_status(safety)

    if reversibility is None:
        reversibility = (
            assess_reversibility_from_facts(git_facts)
            if git_facts is not None
            else empty_reversibility()
        )
    if impact is None:
        impact = empty_impact()
    if external_effects is None:
        external_effects = map_external_effects_from_safety(safety)
    if resource_assessment is None:
        resource_assessment = empty_resource_assessment()

    # Web の Safety 主張は入力に残しても判断根拠にしない
    web_claims = [str(x) for x in (web_safety_claims or []) if str(x).strip()]
    rationale: list[str] = [
        f"mode:{resolved_mode}",
        "phase_d0_skeleton",
        "phase_d1a_observation_only_no_auto_expand",
        "web_safety_claims_not_used_for_policy",
        "llm_not_final_authority_for_policy",
        "resource_unknown_not_treated_as_safe",
        "no_disk_10_percent_rule",
        "no_long_running_immediate_block_rule",
        "no_fixed_resource_thresholds",
    ]
    if web_claims:
        rationale.append("web_safety_claims_received_but_ignored")
    if observation:
        rationale.append("d1a_observation_attached_not_used_for_allow")

    policy_decision, allow_execute, pass_codes = _passthrough_decision(gate)
    rationale.extend(pass_codes)

    # Trusted Personal でも D-0/D-1a は Gate 許可集合を広げない
    if resolved_mode == MODE_TRUSTED_PERSONAL:
        rationale.append("trusted_personal_mode_no_auto_expand_phase_d0")
        # machine safe 経路を不必要に CONFIRM へ落とさない
        if gate.get("allow_execute") and machine == SAFE:
            policy_decision = POLICY_AUTO
            allow_execute = True
            rationale.append("machine_safe_path_not_downgraded_to_confirm")

    # dangerous / risky は LLM・リソース・可逆性でも AUTO にしない
    if machine in (DANGEROUS, RISKY):
        if policy_decision in (POLICY_AUTO, POLICY_MONITORED):
            policy_decision = POLICY_BLOCK
            allow_execute = False
            rationale.append("block_prevent_auto_for_machine_dangerous_or_risky")
        rationale.append("machine_dangerous_or_risky_never_auto_phase_d0")

    # machine unknown を resource/reversibility で safe 扱いにしない
    if machine == UNKNOWN:
        rationale.append("machine_unknown_not_promoted_to_safe")
        rs = (resource_assessment.get("resource_safety") or {}).get("status")
        if rs == RESOURCE_UNKNOWN:
            rationale.append("resource_unknown_kept")
        if reversibility.get("status") == REV_UNKNOWN:
            rationale.append("reversibility_unknown_kept")
        # Gate が allow していない限り AUTO にしない
        if not gate.get("allow_execute") and policy_decision == POLICY_AUTO:
            policy_decision = POLICY_BLOCK
            allow_execute = False
            rationale.append("block_prevent_auto_without_gate_allow")

    # LLM read_only_likely だけでは AUTO にしない
    analysis = llm_bundle.get("analysis") or {}
    if analysis.get("read_only_likely") and not gate.get("allow_execute"):
        if policy_decision == POLICY_AUTO:
            policy_decision = POLICY_BLOCK
            allow_execute = False
        rationale.append("llm_read_only_likely_does_not_grant_auto")

    # 最終: Gate が禁止したものを D-0/D-1a で許可しない（観測でも覆さない）
    if allow_execute and not gate.get("allow_execute"):
        allow_execute = False
        policy_decision = (
            POLICY_CONFIRM
            if str(gate.get("decision")) == "ExperimentCandidate"
            else POLICY_BLOCK
        )
        rationale.append("phase_d0_cannot_override_gate_deny")
        rationale.append("phase_d1a_observation_cannot_override_gate_deny")

    audit = {
        "gate": {
            "decision": gate.get("decision"),
            "allow_execute": gate.get("allow_execute"),
            "rationale_codes": gate.get("rationale_codes"),
        },
        "compatibility": compatibility,
        "machine_safety": {
            "machine_assessed": machine,
            "status": safety.get("status"),
            "side_effects": safety.get("side_effects"),
            "network_access": safety.get("network_access"),
            "privilege": safety.get("privilege"),
        },
        "llm_analysis": {
            "ok": llm_bundle.get("ok"),
            "skipped": llm_bundle.get("skipped"),
            "read_only_likely": analysis.get("read_only_likely"),
            "not_a_safety_proof": True,
        },
        "reversibility": reversibility,
        "impact": impact,
        "external_effects": external_effects,
        "resource_assessment": resource_assessment,
        "git_facts": git_facts,
        "observation": observation,
        "execution_id": execution_id,
        "policy_decision": policy_decision,
        "allow_execute": allow_execute,
        "rationale_codes": rationale,
        "web_safety_claims_used": False,
        "web_safety_claims_ignored": web_claims,
        "candidate_command": (candidate or {}).get("command"),
        "phase": PHASE_D1A,
        "mode": resolved_mode,
        "auto_range_expanded": False,
        "disk_10_percent_rule_applied": False,
        "long_running_immediate_block_applied": False,
        "resource_unknown_treated_as_safe": False,
        "machine_safe_path_downgraded_to_confirm": False,
        "observation_affects_allow_execute": False,
    }
    if gate.get("allow_execute") and machine == SAFE and policy_decision == POLICY_AUTO:
        audit["machine_safe_path_downgraded_to_confirm"] = False

    return {
        "phase": PHASE_D1A,
        "mode": resolved_mode,
        "decision": policy_decision,
        "allow_execute": allow_execute,
        "execution_control": {
            "decision": policy_decision,
            "allow_execute": allow_execute,
            "monitored": policy_decision == POLICY_MONITORED,
            "requires_human_confirm": policy_decision == POLICY_CONFIRM,
        },
        "gate": gate,
        "compatibility": compatibility,
        "machine_safety": safety,
        "llm_analysis": llm_bundle,
        "reversibility": reversibility,
        "impact": impact,
        "external_effects": external_effects,
        "resource_assessment": resource_assessment,
        "git_facts": git_facts,
        "observation": observation,
        "execution_id": execution_id,
        "rationale_codes": rationale,
        "audit": audit,
        "assert_not_safety_proof": True,
        "not_merged_into_machine_safety": True,
        "observation_only_phase_d1a": True,
    }
