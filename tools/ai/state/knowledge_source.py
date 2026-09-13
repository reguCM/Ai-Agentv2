"""
Knowledge Source Selection / Evidence / Action Value — 観測層（Phase KSS-0）。

行動は変更しない。評価値と provenance を記録し、将来の Decision Policy 校正用データを蓄える。
Prompt には載せない（Phase 4 headroom 保護）。

Env:
  AI_AGENT_KNOWLEDGE_SOURCE_OBS=1 で観測 ON（既定 OFF）。
"""

from __future__ import annotations

import os
import re
from collections import Counter
from urllib.parse import urlparse

from tools.ai.state.memory_recall import (
    assess_information_gain,
    command_family,
    count_family_streak,
    open_question_fail_counts,
)
from tools.ai.state.retrieve import count_consecutive_failures, event_error_class

SOURCES = (
    "state",
    "history",
    "external_research",
    "llm_reasoning",
    "experiment",
)

# 公式っぽい host の粗いヒューリスティック（固定信頼スコアにはしない）
_OFFICIAL_HOST_HINTS = (
    "learn.microsoft.com",
    "docs.microsoft.com",
    "microsoft.com",
    "github.com",
    "raw.githubusercontent.com",
    "developer.nvidia.com",
    "docs.python.org",
)
_COMMUNITY_HOST_HINTS = (
    "stackoverflow.com",
    "stackexchange.com",
    "superuser.com",
    "reddit.com",
)
_IMPL_HINT_RE = re.compile(
    r"github\.com|gist\.github|example|sample|snippet|Get-\w+|Win32_\w+|nvidia-smi|wmic",
    re.I,
)


def knowledge_source_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KNOWLEDGE_SOURCE_OBS")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _clamp01(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def assess_known_coverage(state):
    """
    現在の問題に対する既知知識のカバレッジ（探索指標）。
    正解率ではない。
    """
    selected = list(getattr(state, "selected_findings", None) or [])
    open_qs = [
        q
        for q in (getattr(state, "open_questions", None) or [])
        if isinstance(q, dict) and str(q.get("status") or "open") == "open"
    ]
    history = getattr(state, "research_history", None)
    events = list(getattr(history, "events", None) or [])
    fails = [
        e
        for e in events
        if e.get("type") == "verify_fail"
        or (isinstance(e.get("result"), dict) and e.get("result", {}).get("ok") is False)
    ]
    oks = [
        e
        for e in events
        if e.get("type") == "verify_ok"
        or (isinstance(e.get("result"), dict) and e.get("result", {}).get("ok") is True)
    ]
    info = assess_information_gain(state) if state is not None else {}
    err_streak, err_cls = count_consecutive_failures(history, by="error_class")
    fam_streak, fam_key = count_family_streak(history)
    q_fails = open_question_fail_counts(state) if state is not None else []

    has_usable = len(selected) > 0
    has_success = len(oks) > 0
    fails_only = len(fails) > 0 and not has_success
    same_error = err_streak >= 2
    same_oq = any((q.get("fail_count") or 0) >= 2 for q in q_fails)
    no_gain = bool(info.get("no_gain"))

    # 粗い coverage: usable/成功があれば高め、失敗のみ・no_gain なら低め
    score = 0.15
    reasons = []
    if has_usable:
        score += 0.45
        reasons.append("has_selected_usable")
    if has_success:
        score += 0.25
        reasons.append("history_has_verify_ok")
    if fails_only:
        score -= 0.15
        reasons.append("history_fails_only")
    if same_error:
        score -= 0.1
        reasons.append(f"error_class_streak:{err_cls}")
    if same_oq:
        score -= 0.1
        reasons.append("open_question_loop")
    if no_gain:
        score -= 0.15
        reasons.append("no_information_gain")
    if fam_streak >= 2:
        score -= 0.05
        reasons.append(
            f"family_streak:{fam_key[0] if fam_key else ''}/{fam_key[1] if fam_key else ''}"
        )
    score = _clamp01(score)

    return {
        "known_coverage": score,
        "known_coverage_note": "exploration_signal_not_accuracy",
        "has_usable_in_state": has_usable,
        "has_success_in_history": has_success,
        "history_fails_only": fails_only,
        "same_error_class_continuing": same_error,
        "stuck_error_class": err_cls if same_error else None,
        "same_open_question_continuing": same_oq,
        "command_family_no_gain": bool(fam_streak >= 2 and no_gain),
        "no_gain": no_gain,
        "information_gain": {
            "has_gain": info.get("has_gain"),
            "no_gain": info.get("no_gain"),
            "reasons_gain": info.get("reasons_gain"),
            "reasons_stuck": info.get("reasons_stuck"),
        },
        "open_question_count": len(open_qs),
        "verify_ok_count": len(oks),
        "verify_fail_count": len(fails),
        "reasons": reasons,
        "estimate_method": "heuristic_v0",
        "not_for_decision": True,
    }


def score_knowledge_sources(state, coverage=None, *, web_hit_count=0):
    """
    各知識源の相対価値（観測用）。自動切替はしない。
    """
    coverage = coverage or assess_known_coverage(state)
    values = {s: 0.2 for s in SOURCES}
    reasons = {s: [] for s in SOURCES}

    if coverage.get("has_usable_in_state"):
        values["state"] += 0.55
        reasons["state"].append("usable_present")
        values["history"] += 0.1
        reasons["history"].append("usable_linked")
    if coverage.get("has_success_in_history"):
        values["history"] += 0.25
        reasons["history"].append("prior_success")
        if not coverage.get("has_usable_in_state"):
            values["history"] += 0.15
            reasons["history"].append("success_without_selected")
    if coverage.get("history_fails_only") or coverage.get("no_gain"):
        values["external_research"] += 0.35
        reasons["external_research"].append("no_local_success_or_no_gain")
        values["experiment"] += 0.15
        reasons["experiment"].append("need_new_route")
        values["llm_reasoning"] -= 0.05
        reasons["llm_reasoning"].append("avoid_blind_retry")
    if coverage.get("same_error_class_continuing"):
        values["external_research"] += 0.2
        reasons["external_research"].append("repeated_error_class")
        values["experiment"] += 0.2
        reasons["experiment"].append("pivot_experiment")
    if coverage.get("same_open_question_continuing"):
        values["external_research"] += 0.1
        reasons["external_research"].append("open_question_loop")
    if not coverage.get("has_success_in_history") and not coverage.get(
        "has_usable_in_state"
    ):
        values["external_research"] += 0.25
        reasons["external_research"].append("no_known_success")
        values["llm_reasoning"] += 0.1
        reasons["llm_reasoning"].append("initial_hypothesis")
    if web_hit_count > 0:
        values["external_research"] += 0.05
        reasons["external_research"].append("hits_available")
        # 外部はあるが適用が不明なら experiment も上げる
        if coverage.get("no_gain"):
            values["experiment"] += 0.15
            reasons["experiment"].append("hits_but_no_gain")

    for s in SOURCES:
        values[s] = _clamp01(values[s])

    ranked = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "source_values": values,
        "source_reasons": reasons,
        "preferred_source": ranked[0][0] if ranked else None,
        "ranking": [{"source": s, "value": v} for s, v in ranked],
        "auto_switch": False,
        "estimate_method": "heuristic_v0",
        "not_for_decision": True,
    }


def classify_source_reliability(url, backend=None):
    """カテゴリのみ。数値の公式信頼度表はまだ持たない。"""
    host = ""
    try:
        host = (urlparse(str(url or "")).hostname or "").lower()
    except Exception:
        host = ""
    backend = str(backend or "").lower()
    if any(h in host for h in _OFFICIAL_HOST_HINTS):
        category = "official_or_vendor_docs"
    elif any(h in host for h in _COMMUNITY_HOST_HINTS):
        category = "community_qna"
    elif "github.com" in host:
        category = "public_repository"
    elif host:
        category = "web_page"
    else:
        category = "unknown"
    if backend == "learn_microsoft":
        category = "official_or_vendor_docs"
    return {
        "category": category,
        "host": host or None,
        "backend": backend or None,
        "numeric_score": None,
        "note": "category_only_no_fixed_score",
    }


def assess_hit_evidence(hit, *, open_questions=None, goal_text=None):
    """単一 hit の evidence 軸（独立値）。"""
    hit = hit or {}
    title = str(hit.get("title") or "")
    snippet = str(hit.get("snippet") or "")
    url = str(hit.get("url") or "")
    text = f"{title} {snippet}".lower()
    reliability = classify_source_reliability(url, hit.get("backend"))

    q_terms = []
    for q in open_questions or []:
        raw = str(q.get("text") or q.get("question") or "")
        q_terms.extend(re.findall(r"[A-Za-z_]{3,}|\w{2,}", raw))
    if goal_text:
        q_terms.extend(re.findall(r"[A-Za-z_]{3,}|\w{2,}", str(goal_text)))
    q_terms = [t.lower() for t in q_terms if t]
    overlap = sum(1 for t in set(q_terms) if t in text) if q_terms else 0
    relevance = _clamp01(overlap / max(len(set(q_terms)), 1)) if q_terms else None

    impl = bool(_IMPL_HINT_RE.search(text) or _IMPL_HINT_RE.search(url))
    claim_support = None
    if relevance is not None:
        claim_support = _clamp01(0.3 + 0.5 * relevance + (0.2 if impl else 0.0))

    return {
        "url": url[:300] if url else None,
        "title": title[:200] if title else None,
        "backend": hit.get("backend"),
        "source_reliability": reliability,
        "evidence_relevance": relevance,
        "claim_support": claim_support,
        "implementation_precedent": {
            "exists": impl,
            "same_platform": "windows" in text or "powershell" in text or "win32" in text,
            "same_environment": None,
            "runnable_example": bool(re.search(r"Get-\w+|nvidia-smi|wmic", text)),
            "signals": ["keyword_heuristic"] if impl else [],
        },
        "estimate_method": "heuristic_v0",
        "not_for_decision": True,
    }


def assess_external_research_bundle(hits, *, open_questions=None, goal_text=None):
    """検索結果集合の provenance。転載の粗い区別は host 多様性。"""
    assessed = [
        assess_hit_evidence(h, open_questions=open_questions, goal_text=goal_text)
        for h in (hits or [])[:12]
    ]
    hosts = []
    for item in assessed:
        host = (item.get("source_reliability") or {}).get("host")
        if host:
            hosts.append(host)
    host_counts = Counter(hosts)
    unique_hosts = len(host_counts)
    independent_confirmation = {
        "unique_hosts": unique_hosts,
        "host_counts": dict(host_counts),
        "likely_reprint_heavy": unique_hosts <= 1 and len(assessed) >= 3,
        "note": "host_diversity_proxy_not_semantic_dedupe",
    }
    impl_examples = [
        a for a in assessed if (a.get("implementation_precedent") or {}).get("exists")
    ]
    return {
        "hit_count": len(hits or []),
        "assessed_hits": assessed,
        "independent_confirmation": independent_confirmation,
        "implementation_precedent_summary": {
            "exists": len(impl_examples) > 0,
            "independent_examples": len(impl_examples),
            "runnable_example_count": sum(
                1
                for a in impl_examples
                if (a.get("implementation_precedent") or {}).get("runnable_example")
            ),
        },
        "estimate_method": "heuristic_v0",
        "not_for_decision": True,
    }


def estimate_action_value_fields(
    *,
    coverage,
    source_scores,
    external_bundle=None,
    candidate=None,
):
    """
    evidence_confidence と action_value 構成要素を分離して記録。
    Decision には使わない。
    """
    coverage = coverage or {}
    source_scores = source_scores or {}
    external_bundle = external_bundle or {}
    candidate = candidate or {}

    impl = (external_bundle.get("implementation_precedent_summary") or {}).get(
        "exists"
    )
    evidence_confidence = 0.25
    if coverage.get("has_usable_in_state"):
        evidence_confidence += 0.35
    if impl:
        evidence_confidence += 0.2
    if (external_bundle.get("independent_confirmation") or {}).get("unique_hosts", 0) >= 2:
        evidence_confidence += 0.1
    evidence_confidence = _clamp01(evidence_confidence)

    applicability = 0.4
    if coverage.get("no_gain"):
        applicability -= 0.15
    if impl:
        applicability += 0.2
    fam = command_family(candidate)
    if fam != ("", "") and coverage.get("command_family_no_gain"):
        applicability -= 0.2
    applicability = _clamp01(applicability)

    expected_information_gain = 0.35
    if coverage.get("no_gain"):
        preferred = source_scores.get("preferred_source")
        if preferred in ("external_research", "experiment"):
            expected_information_gain = 0.55
        else:
            expected_information_gain = 0.25
    if coverage.get("has_usable_in_state"):
        expected_information_gain = 0.2
    expected_information_gain = _clamp01(expected_information_gain)

    success_probability_estimate = _clamp01(
        0.2 * evidence_confidence + 0.5 * applicability + (0.2 if impl else 0.0)
    )
    repetition_risk = 0.2
    if coverage.get("no_gain"):
        repetition_risk += 0.35
    if coverage.get("same_error_class_continuing"):
        repetition_risk += 0.25
    repetition_risk = _clamp01(repetition_risk)

    return {
        "expected_information_gain": expected_information_gain,
        "success_probability_estimate": success_probability_estimate,
        "evidence_confidence": evidence_confidence,
        "applicability": applicability,
        "implementation_precedent": bool(impl),
        "execution_cost_estimate": "unknown",
        "risk_estimate": "unknown",
        "repetition_risk": repetition_risk,
        # 総合は記録するが Decision 禁止
        "action_value_composite": _clamp01(
            0.35 * expected_information_gain
            + 0.25 * success_probability_estimate
            + 0.2 * applicability
            + 0.2 * evidence_confidence
            - 0.25 * repetition_risk
        ),
        "estimate_method": "heuristic_v0",
        "not_for_decision": True,
    }


def build_proposal_observations(
    candidates,
    *,
    coverage,
    source_scores,
    external_bundle=None,
    preferred_source=None,
):
    """候補ごとの provenance + value 見積（監査用）。"""
    preferred_source = preferred_source or (source_scores or {}).get("preferred_source")
    observations = []
    for idx, cand in enumerate(candidates or []):
        if not isinstance(cand, dict):
            continue
        value_fields = estimate_action_value_fields(
            coverage=coverage,
            source_scores=source_scores,
            external_bundle=external_bundle,
            candidate=cand,
        )
        observations.append(
            {
                "proposal_id": f"cand_{idx}",
                "action": {
                    "command": cand.get("command"),
                    "args": list(cand.get("args") or []),
                    "question": cand.get("question"),
                },
                "rationale": None,
                "evidence": {
                    "state": bool(coverage.get("has_usable_in_state")),
                    "history": bool(
                        coverage.get("has_success_in_history")
                        or coverage.get("verify_fail_count")
                    ),
                    "external_research": bool(
                        (external_bundle or {}).get("hit_count")
                    ),
                    "experiment": True,
                },
                "evidence_sources_used": [
                    s
                    for s, used in {
                        "state": bool(coverage.get("has_usable_in_state")),
                        "history": bool(coverage.get("verify_fail_count")),
                        "external_research": bool(
                            (external_bundle or {}).get("hit_count")
                        ),
                        "llm_reasoning": True,
                        "experiment": True,
                    }.items()
                    if used
                ],
                "preferred_source_at_proposal": preferred_source,
                **value_fields,
            }
        )
    return observations


def calibrate_proposals_with_results(proposal_obs, verified_results, *, coverage_before, coverage_after):
    """Proposal → Action → Result の紐付け（実測）。"""
    verified_results = verified_results or []
    by_key = {}
    for item in verified_results:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        key = (
            str((evidence or {}).get("command") or "").strip(),
            tuple(str(a) for a in ((evidence or {}).get("args") or [])),
        )
        if key[0]:
            by_key[key] = item

    calibrated = []
    usable_before = 1 if coverage_before.get("has_usable_in_state") else 0
    usable_after = 1 if coverage_after.get("has_usable_in_state") else 0
    for prop in proposal_obs or []:
        action = prop.get("action") or {}
        key = (
            str(action.get("command") or "").strip(),
            tuple(str(a) for a in (action.get("args") or [])),
        )
        result = by_key.get(key)
        ok = False
        error_class = None
        if result:
            ok = result.get("confidence") == "high" or (
                isinstance(result.get("evidence"), dict)
                and result.get("confidence") == "high"
            )
            if result.get("confidence") == "high":
                ok = True
            else:
                ok = False
            err = str((result.get("evidence") or {}).get("error") or "")
            from tools.ai.state.retrieve import classify_error_class

            error_class = classify_error_class(err) if not ok else None
        actual_info_gain = None
        if coverage_before and coverage_after:
            actual_info_gain = bool(coverage_after.get("no_gain") is False) and (
                coverage_before.get("no_gain") is True
                or usable_after > usable_before
                or (coverage_after.get("stuck_error_class")
                    != coverage_before.get("stuck_error_class"))
            )
        calibrated.append(
            {
                **prop,
                "actual_success": ok if result is not None else None,
                "actual_error_class": error_class,
                "actual_usable_gain": usable_after > usable_before,
                "actual_information_gain": actual_info_gain,
                "coverage_before_no_gain": coverage_before.get("no_gain"),
                "coverage_after_no_gain": coverage_after.get("no_gain"),
                "result_linked": result is not None,
            }
        )
    return {
        "proposals": calibrated,
        "usable_gain_round": usable_after > usable_before,
        "no_gain_before": coverage_before.get("no_gain"),
        "no_gain_after": coverage_after.get("no_gain"),
    }


def observe_research_round(
    state,
    *,
    hits=None,
    candidates=None,
    verified=None,
    goal_text=None,
    round_num=None,
):
    """1 research ラウンド分の観測バンドル（Prompt 非載荷）。"""
    open_qs = [
        q
        for q in (getattr(state, "open_questions", None) or [])
        if isinstance(q, dict) and str(q.get("status") or "open") == "open"
    ]
    coverage_before = assess_known_coverage(state)
    source_scores = score_knowledge_sources(
        state, coverage_before, web_hit_count=len(hits or [])
    )
    external = assess_external_research_bundle(
        hits, open_questions=open_qs, goal_text=goal_text
    )
    proposals = build_proposal_observations(
        candidates,
        coverage=coverage_before,
        source_scores=source_scores,
        external_bundle=external,
        preferred_source=source_scores.get("preferred_source"),
    )
    # verified 後の coverage は呼び出し側で state 更新後に再計算してもよい
    coverage_after = assess_known_coverage(state)
    calibration = calibrate_proposals_with_results(
        proposals,
        (verified or {}).get("results") if isinstance(verified, dict) else verified,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
    )
    research_cost = {
        "web_hit_count": len(hits or []),
        "candidate_count": len(candidates or []),
        "verified_count": len(
            ((verified or {}).get("results") if isinstance(verified, dict) else verified)
            or []
        ),
        "note": "counts_only_llm_cost_in_timing",
    }
    return {
        "enabled": True,
        "round": round_num,
        "known_coverage": coverage_before,
        "knowledge_source_selection": source_scores,
        "external_research_evidence": external,
        "proposal_observations": proposals,
        "calibration": calibration,
        "research_cost": research_cost,
        "auto_switch": False,
        "prompt_injected": False,
        "not_for_decision": True,
        "phase": "kss-0",
    }


def maybe_observe_research_round(*args, **kwargs):
    if not knowledge_source_obs_enabled():
        return {"enabled": False, "phase": "kss-0"}
    return observe_research_round(*args, **kwargs)


def record_observation_event(state, observation, *, round_num=None):
    """History に観測イベントを追記（Prompt 非載荷）。"""
    if not observation or not observation.get("enabled"):
        return None
    history = getattr(state, "research_history", None)
    if history is None or not hasattr(history, "append"):
        return None
    sel = observation.get("knowledge_source_selection") or {}
    cov = observation.get("known_coverage") or {}
    return history.append(
        "knowledge_source_obs",
        action={"kind": "observe"},
        result={
            "preferred_source": sel.get("preferred_source"),
            "known_coverage": cov.get("known_coverage"),
            "no_gain": cov.get("no_gain"),
            "source_values": sel.get("source_values"),
        },
        metadata={
            "round": round_num,
            "not_for_decision": True,
            "phase": "kss-0",
        },
    )
