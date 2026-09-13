"""
KSS-1.1: Decision Evidence & Confidence Audit（観測のみ）。

既存パイプラインが OK/NG/継続/停止等を決める際に使っている
根拠・閾値・verifier confidence・reason を写す。
LLM 自己申告 confidence を正式な信頼度とは扱わない。
存在しない値は missing（0 に埋めない）。

Env: AI_AGENT_KSS11_OBS=1（既定 OFF）。
"""

from __future__ import annotations

import os
import uuid
from collections import Counter

# 既存定数の記録用（再発明しない）
VERIFY_CONFIDENCE_LABELS = ("high", "medium", "low")
PROGRESS_ACTIONS = ("implement", "continue", "stop")
HIGH_LABEL = "high"
MEDIUM_LABEL = "medium"
LOW_LABEL = "low"

EXISTING_TO_OBS_MAPPING = {
    "verified.results[].confidence": "verify_confidence_label",
    "usable_findings / reference / unresolved": "finding_bucket_counts",
    "evaluate_research_progress.action": "progress_action",
    "evaluate_research_progress.reason": "progress_reason",
    "judgment.satisfies_request": "judge_satisfies_request",
    "judgment.missing": "judge_missing",
    "live_skip / llm judge": "judge_source",
    "gj_trigger.would_skip / triggers": "gj_would_skip / gj_triggers",
    "escalation.reason / routine": "escalation_reason / escalation_routine",
    "filter_rejected_candidates": "candidates_rejected_count",
    "hit_score / kept hits": "web_hit_scores / web_kept_count",
    "validate_tool_spec / completeness": "proposal_spec_status / proposal_completeness_ok",
    "fail_stage": "fail_stage",
    "assess_information_gain.no_gain": "no_gain",
    "KSS-0 known_coverage": "kss0_known_coverage",
    "KSS-1 llm self confidence": "llm_self_confidence (auxiliary_only)",
    "MAX_RESEARCH_ROUNDS / MAX_STAGNATION": "threshold_refs.max_rounds / max_stagnation",
    "VERIFY high/low only": "verify_confidence_numeric = missing",
    "HELP / human escalate": "missing (enum only)",
}


MISSING_FIELDS = [
    "llm_judge_confidence_numeric",
    "progress_decision_confidence",
    "proposal_decision_confidence",
    "verify_confidence_numeric",
    "help_escalation_decision",
    "partial_llm_judgment",
    "judge_accept_weights",
    "official_source_reliability_numeric_table",
    "composite_web_confidence",
    "composite_decision_confidence",
]


def kss11_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS11_OBS")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _new_id(prefix="de"):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _missing():
    return "missing"


def evidence_level_from_existing(
    *,
    usable_count=0,
    reference_count=0,
    unresolved_count=0,
    verify_high=0,
    verify_low=0,
    web_kept=0,
):
    """
    既存ラベルからの粗い強度バケットのみ。
    数値 confidence を発明しない。
    """
    if verify_high or usable_count:
        return "high"
    if reference_count or web_kept:
        return "medium"
    if verify_low or unresolved_count:
        return "low"
    return "missing"


def collect_verify_evidence(verified):
    results = []
    if isinstance(verified, dict):
        results = list(verified.get("results") or [])
    elif isinstance(verified, list):
        results = verified
    high = low = other = 0
    labels = []
    for item in results:
        conf = item.get("confidence")
        labels.append(conf if conf is not None else _missing())
        if conf == HIGH_LABEL:
            high += 1
        elif conf == LOW_LABEL:
            low += 1
        elif conf == MEDIUM_LABEL:
            other += 1
        else:
            other += 1
    return {
        "evidence_count": len(results),
        "successful_evidence_count": high,
        "failed_evidence_count": low,
        "verify_high_count": high,
        "verify_low_count": low,
        "verify_other_or_missing_count": other,
        "verify_confidence_labels": labels,
        "verify_confidence_numeric": _missing(),
        "verifier_support": high > 0,
        "tool_result_support": high > 0,
    }


def collect_pack_evidence(research):
    research = research or {}
    usable = list(research.get("usable_findings") or [])
    reference = list(research.get("reference_findings") or [])
    unresolved = list(research.get("unresolved") or [])
    insufficient = list(research.get("insufficient_findings") or [])
    return {
        "usable_count": len(usable),
        "reference_count": len(reference),
        "unresolved_count": len(unresolved),
        "insufficient_count": len(insufficient),
        "finding_bucket_counts": {
            "usable": len(usable),
            "reference": len(reference),
            "unresolved": len(unresolved),
            "insufficient": len(insufficient),
        },
        "local_history_support": _missing(),  # 明示フラグは別経路
    }


def collect_web_evidence(web_hits, web_exec=None):
    hits = list(web_hits or [])
    scores = []
    # 保存済み score を優先。無ければ既存 hit_score() で観測用に再計算（routing には使わない）
    hit_score_fn = None
    try:
        from tools.system.tool_builder.research.web import hit_score as hit_score_fn
    except Exception:
        hit_score_fn = None
    for hit in hits:
        if not isinstance(hit, dict):
            scores.append(_missing())
            continue
        if "score" in hit and hit.get("score") is not None:
            scores.append(hit.get("score"))
        elif hit_score_fn is not None:
            try:
                scores.append(hit_score_fn(hit))
            except Exception:
                scores.append(_missing())
        else:
            scores.append(_missing())
    dropped = None
    if isinstance(web_exec, dict):
        # results 内 dropped_count があれば合算
        total_dropped = 0
        found = False
        for item in web_exec.get("results") or []:
            if isinstance(item, dict) and item.get("dropped_count") is not None:
                total_dropped += int(item.get("dropped_count") or 0)
                found = True
        dropped = total_dropped if found else _missing()
    return {
        "external_source_count": len(hits),
        "web_kept_count": len(hits),
        "web_dropped_count": dropped if dropped is not None else _missing(),
        "web_hit_scores": scores,
        "source_count": len(hits),
        "independent_evidence_count": _missing(),
        "contradictory_evidence_count": _missing(),
    }


def classify_decision_source(
    *,
    has_llm_judgment=False,
    has_verifier=False,
    has_rule=False,
):
    flags = sum(bool(x) for x in (has_llm_judgment, has_verifier, has_rule))
    if flags >= 2:
        return "mixed"
    if has_verifier:
        return "verifier"
    if has_llm_judgment:
        return "llm_judgment"
    if has_rule:
        return "deterministic_rule"
    return _missing()


def build_threshold_refs(*, max_rounds=None, max_stagnation=None, verify_timeout=None):
    return {
        "max_research_rounds": max_rounds if max_rounds is not None else _missing(),
        "max_stagnation": max_stagnation if max_stagnation is not None else _missing(),
        "verify_timeout": verify_timeout if verify_timeout is not None else _missing(),
        "verify_confidence_gate": "confidence == 'high' → usable",
        "progress_implement_if_satisfies_or_missing_resolved": True,
        "note": "values copied from existing constants/rules; not invented weights",
    }


def capture_research_round_evidence(
    *,
    round_num,
    researched=None,
    candidates_before_filter=None,
    candidates_after_filter=None,
    judgment=None,
    gj_trigger=None,
    gj_result=None,
    progress_decision=None,
    rule_partial=None,
    kss0=None,
    kss1=None,
    max_rounds=None,
    max_stagnation=None,
):
    """1 research ラウンドの decision evidence バンドル。"""
    researched = researched or {}
    verified = researched.get("verified")
    research = researched.get("research") or {}
    verify_ev = collect_verify_evidence(verified)
    pack_ev = collect_pack_evidence(research)
    web_ev = collect_web_evidence(
        researched.get("web_hits"), researched.get("web") or researched.get("local")
    )
    # web_exec は run_research 戻りに無い場合あり → missing 許容

    cand_in = len(candidates_before_filter) if candidates_before_filter is not None else (
        len(researched.get("candidates") or [])
    )
    cand_out = len(candidates_after_filter) if candidates_after_filter is not None else cand_in
    rejected = (
        cand_in - cand_out
        if candidates_before_filter is not None and candidates_after_filter is not None
        else _missing()
    )

    judgment = judgment or {}
    live_skipped = bool((gj_result or {}).get("live_skipped"))
    audit_only = bool((gj_result or {}).get("audit_only"))
    if live_skipped:
        judge_source = "live_skip"
    elif audit_only:
        judge_source = "audit_shadow"
    elif judgment:
        judge_source = "llm"
    else:
        judge_source = _missing()

    escalation = (rule_partial or {}).get("escalation") or {}
    progress_decision = progress_decision or {}

    evidence_level = evidence_level_from_existing(
        usable_count=pack_ev["usable_count"],
        reference_count=pack_ev["reference_count"],
        unresolved_count=pack_ev["unresolved_count"],
        verify_high=verify_ev["verify_high_count"],
        verify_low=verify_ev["verify_low_count"],
        web_kept=web_ev["web_kept_count"] if isinstance(web_ev["web_kept_count"], int) else 0,
    )

    kss0 = kss0 or researched.get("knowledge_source_observation") or {}
    kss1 = kss1 or researched.get("decision_confidence_observation") or {}
    no_gain = None
    if isinstance(kss0, dict):
        no_gain = (kss0.get("known_coverage") or {}).get("no_gain")
        if no_gain is None and kss0.get("known_coverage_after"):
            no_gain = (kss0.get("known_coverage_after") or {}).get("no_gain")

    llm_self = {
        "action_confidence": _missing(),
        "observation_coverage": _missing(),
        "auxiliary_only": True,
        "not_formal_confidence": True,
    }
    if isinstance(kss1, dict) and kss1.get("enabled"):
        cal = kss1.get("calibration_summary") or {}
        llm_self["observation_coverage"] = cal.get("observation_coverage")
        # 代表値は取らない。decisions 内の有無だけ
        present = cal.get("decisions_with_observation")
        llm_self["decisions_with_observation"] = (
            present if present is not None else _missing()
        )
        llm_self["decisions_total"] = cal.get("decisions_total")
        if present == 0:
            llm_self["action_confidence"] = _missing()

    decision_id = _new_id("decision")
    events = []

    # verify decision
    events.append(
        {
            "decision_id": f"{decision_id}_verify",
            "round": round_num,
            "decision_type": "verify_batch",
            "decision_source": "verifier",
            "final_decision": "has_high" if verify_ev["verify_high_count"] else "no_high",
            "evidence_refs": verify_ev,
            "threshold_refs": {
                "usable_requires": "confidence == high",
            },
            "reason_codes": [],
        }
    )

    # judge decision
    events.append(
        {
            "decision_id": f"{decision_id}_judge",
            "round": round_num,
            "decision_type": "research_judge",
            "decision_source": classify_decision_source(
                has_llm_judgment=judge_source == "llm",
                has_rule=judge_source in ("live_skip", "audit_shadow"),
            ),
            "judge_source": judge_source,
            "final_decision": bool(judgment.get("satisfies_request"))
            if "satisfies_request" in judgment
            else _missing(),
            "judge_satisfies_request": judgment.get("satisfies_request"),
            "judge_missing": list(judgment.get("missing") or []),
            "judge_reason": judgment.get("reason"),
            "score_refs": {"llm_judge_confidence_numeric": _missing()},
            "gj_needed": (gj_trigger or {}).get("needed"),
            "gj_would_skip": (gj_trigger or {}).get("would_skip"),
            "gj_triggers": (gj_trigger or {}).get("triggers"),
            "gj_skip_triggers": (gj_trigger or {}).get("skip_triggers"),
        }
    )

    # progress decision
    events.append(
        {
            "decision_id": f"{decision_id}_progress",
            "round": round_num,
            "decision_type": "research_progress",
            "decision_source": "deterministic_rule",
            "final_decision": progress_decision.get("action") or _missing(),
            "progress_action": progress_decision.get("action"),
            "progress_reason": progress_decision.get("reason"),
            "progress_stagnation": progress_decision.get("stagnation"),
            "progress_has_new_finding": progress_decision.get("has_new_finding"),
            "progress_missing_same": progress_decision.get("missing_same"),
            "progress_duplicate_only": progress_decision.get("duplicate_only"),
            "threshold_refs": build_threshold_refs(
                max_rounds=max_rounds, max_stagnation=max_stagnation
            ),
            "score_refs": {"progress_decision_confidence": _missing()},
        }
    )

    return {
        "enabled": True,
        "phase": "kss-1.1",
        "not_for_decision": True,
        "behavior_changed": False,
        "round": round_num,
        "bundle_id": decision_id,
        "evidence": {
            **verify_ev,
            **pack_ev,
            **web_ev,
            "candidates_in_count": cand_in,
            "candidates_out_count": cand_out,
            "candidates_rejected_count": rejected,
            "evidence_level": evidence_level,
            "direct_observation_support": verify_ev["verify_high_count"] > 0,
            "no_gain": no_gain if no_gain is not None else _missing(),
            "kss0_known_coverage": (
                (kss0.get("known_coverage") or {}).get("known_coverage")
                if isinstance(kss0, dict)
                else _missing()
            ),
            "kss0_preferred_source": (
                (kss0.get("knowledge_source_selection") or {}).get("preferred_source")
                if isinstance(kss0, dict)
                else _missing()
            ),
            "web_decision_link": (
                researched.get("web_decision_link")
                if isinstance(researched.get("web_decision_link"), dict)
                else _missing()
            ),
        },
        "escalation": {
            "reason": escalation.get("reason"),
            "routine": escalation.get("routine"),
            "needs_partial_llm": escalation.get("needs_partial_llm"),
            "needs_global_judge": escalation.get("needs_global_judge"),
        },
        "llm_self_assessment_auxiliary": llm_self,
        "decision_events": events,
        "mapping_note": "see EXISTING_TO_OBS_MAPPING",
        "missing_fields_policy": "missing_not_zero",
    }


def capture_proposal_evidence(*, proposal_validation=None, completeness=None, fail_stage=None):
    proposal_validation = proposal_validation or {}
    completeness = completeness or {}
    return {
        "enabled": True,
        "phase": "kss-1.1",
        "decision_type": "proposal_validation",
        "decision_source": "mixed",
        "proposal_spec_status": proposal_validation.get("status")
        if proposal_validation.get("status") is not None
        else _missing(),
        "proposal_spec_errors": list(proposal_validation.get("errors") or [])
        if "errors" in proposal_validation
        else _missing(),
        "proposal_completeness_ok": completeness.get("ok")
        if "ok" in completeness
        else _missing(),
        "fail_stage": fail_stage if fail_stage is not None else _missing(),
        "score_refs": {"proposal_decision_confidence": _missing()},
        "not_for_decision": True,
    }


def summarize_decision_evidence(bundles):
    """measurement / analysis 用集計。"""
    bundles = [b for b in (bundles or []) if isinstance(b, dict) and b.get("enabled")]
    decision_count = 0
    source_dist = Counter()
    evidence_levels = Counter()
    failure_by_level = Counter()
    success_by_level = Counter()
    threshold_present = 0
    provenance_ok = 0
    high_evidence_failure = 0
    low_evidence_success = 0
    missing_info = 0
    no_gain_n = 0

    for bundle in bundles:
        events = bundle.get("decision_events") or []
        decision_count += len(events)
        for ev in events:
            src = ev.get("decision_source") or _missing()
            source_dist[src] += 1
            if ev.get("threshold_refs"):
                threshold_present += 1
            if ev.get("decision_id") and ev.get("decision_type"):
                provenance_ok += 1

        evd = bundle.get("evidence") or {}
        level = evd.get("evidence_level") or _missing()
        evidence_levels[level] += 1
        if evd.get("no_gain") is True:
            no_gain_n += 1
        if evd.get("no_gain") == _missing() or evd.get("insufficient_count"):
            if evd.get("no_gain") == _missing():
                missing_info += 1

        # progress final as round outcome proxy
        progress = next(
            (
                e
                for e in events
                if e.get("decision_type") == "research_progress"
            ),
            None,
        )
        action = (progress or {}).get("progress_action")
        if action == "implement":
            success_by_level[level] += 1
            if level in ("low", "missing"):
                low_evidence_success += 1
        elif action in ("stop", "continue"):
            # continue は最終失敗ではないが、stop を failure 側に
            if action == "stop":
                failure_by_level[level] += 1
                if level == "high":
                    high_evidence_failure += 1

    return {
        "decision_count": decision_count,
        "bundle_count": len(bundles),
        "decision_source_distribution": dict(source_dist),
        "evidence_coverage": {
            "levels": dict(evidence_levels),
            "rounds_with_evidence_bundle": len(bundles),
        },
        "provenance_coverage": {
            "events_with_id_and_type": provenance_ok,
            "events_total": decision_count,
            "rate": round(provenance_ok / decision_count, 3) if decision_count else None,
        },
        "threshold_coverage": {
            "events_with_threshold_refs": threshold_present,
            "events_total": decision_count,
            "rate": round(threshold_present / decision_count, 3) if decision_count else None,
        },
        "high_evidence_failure_count": high_evidence_failure,
        "low_evidence_success_count": low_evidence_success,
        "contradictory_evidence_count": _missing(),
        "missing_information_count": missing_info,
        "no_gain_round_count": no_gain_n,
        "failure_by_evidence_level": dict(failure_by_level),
        "success_by_evidence_level": dict(success_by_level),
        "existing_to_obs_mapping": EXISTING_TO_OBS_MAPPING,
        "missing_fields": MISSING_FIELDS,
        "not_for_decision": True,
        "phase": "kss-1.1",
    }


def record_decision_evidence_event(state, bundle, *, round_num=None):
    if not bundle or not bundle.get("enabled"):
        return None
    history = getattr(state, "research_history", None)
    if history is None or not hasattr(history, "append"):
        return None
    evd = bundle.get("evidence") or {}
    return history.append(
        "decision_evidence_obs",
        action={"kind": "observe"},
        result={
            "evidence_level": evd.get("evidence_level"),
            "verify_high_count": evd.get("verify_high_count"),
            "usable_count": evd.get("usable_count"),
            "no_gain": evd.get("no_gain"),
            "progress_action": next(
                (
                    e.get("progress_action")
                    for e in (bundle.get("decision_events") or [])
                    if e.get("decision_type") == "research_progress"
                ),
                _missing(),
            ),
        },
        metadata={
            "round": round_num,
            "bundle_id": bundle.get("bundle_id"),
            "not_for_decision": True,
            "phase": "kss-1.1",
        },
    )
