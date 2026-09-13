"""Global Judge の trigger 判定と live skip / shadow audit。

Phase 3.5 以降の通常経路:
  live skip ON（AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP=0 でオフ）
  audit 既定 3（AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE で変更）
"""

import os

SHADOW_MODE = "shadow"
LIVE_SKIP_MODE = "live_skip"

# escalation.reason 値（rule_partial と一致）
REASON_VERIFY_FAIL_ROUTINE = "verify_fail_open_questions_updated"
REASON_USABLE_GOAL = "usable_needs_goal_check"
REASON_EMPTY_ROUND = "empty_round_needs_review"
REASON_AMBIGUOUS_REF = "ambiguous_reference_only"

# trigger id（記録・分析用）
TRIGGER_PARTIAL_LLM_UNAVAILABLE = "partial_llm_unavailable"
TRIGGER_USABLE_NEEDS_GOAL = "usable_needs_goal_check"
TRIGGER_EMPTY_ROUND = "empty_round_needs_review"
TRIGGER_FIRST_ROUND = "first_round"
TRIGGER_FINAL_ROUND = "final_round"
TRIGGER_STAGNATION_RISK = "stagnation_risk"
TRIGGER_ROUTINE_VERIFY_FAIL = "routine_verify_fail_only"
TRIGGER_NON_ROUTINE_ESCALATION = "non_routine_escalation"
TRIGGER_CANDIDATES_ERROR = "candidates_error"
TRIGGER_SHADOW_DEFAULT = "shadow_default_conservative"


def is_live_skip_enabled():
    """
    Phase 3.5 以降: live skip が通常経路。
    オフにするときだけ AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP=0。
    """
    raw = os.environ.get("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def get_audit_rate():
    raw = os.environ.get("AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE", "3")
    try:
        rate = int(str(raw or "3").strip())
    except ValueError:
        rate = 3
    return max(1, rate)


def should_audit_skip_round(round_num, audit_rate=None):
    """互換: ラウンド番号ベース（final round と衝突しやすい）。"""
    rate = audit_rate if audit_rate is not None else get_audit_rate()
    return int(round_num or 0) > 0 and (int(round_num) % rate == 0)


def should_audit_skip_event(skip_event_index, audit_rate=None):
    """live skip 中、N 回目の skip イベントで audit Judge を実行する。"""
    rate = audit_rate if audit_rate is not None else get_audit_rate()
    index = int(skip_event_index or 0)
    return index > 0 and (index % rate == 0)


def _open_question_texts(state):
    return [
        str(q.get("text") or "").strip()
        for q in (getattr(state, "open_questions", None) or [])
        if q.get("status") == "open" and str(q.get("text") or "").strip()
    ]


def build_shadow_judgment(state, escalation=None, *, live_skip=False):
    """
    Global Judge をスキップした場合に機械側が使う judgment。
    保守的に satisfies_request=False、missing=open_questions。
    """
    escalation = escalation or {}
    missing = _open_question_texts(state)
    judgment = {
        "satisfies_request": False,
        "reason": f"{'live_skip' if live_skip else 'shadow'}:{escalation.get('reason') or 'rule_partial'}",
        "missing": missing,
        "proposed_decisions": [],
    }
    if live_skip:
        judgment["live_skip"] = True
    else:
        judgment["shadow"] = True
    return judgment


def compare_shadow_vs_actual(
    shadow_judgment,
    actual_judgment,
    *,
    progress_context=None,
):
    """shadow / live_skip 時と実 Judge の差分。品質確認用。"""
    shadow = shadow_judgment or {}
    actual = actual_judgment or {}
    shadow_missing = tuple(
        sorted(
            str(x).strip().lower()
            for x in (shadow.get("missing") or [])
            if str(x).strip()
        )
    )
    actual_missing = tuple(
        sorted(
            str(x).strip().lower()
            for x in (actual.get("missing") or [])
            if str(x).strip()
        )
    )

    shadow_sat = bool(shadow.get("satisfies_request"))
    actual_sat = bool(actual.get("satisfies_request"))

    critical_miss = (not shadow_sat) and actual_sat
    false_continue = shadow_sat and (not actual_sat)

    result = {
        "satisfies_request_match": shadow_sat == actual_sat,
        "missing_match": shadow_missing == actual_missing,
        "critical_miss": critical_miss,
        "false_continue": false_continue,
        "shadow_satisfies": shadow_sat,
        "actual_satisfies": actual_sat,
        "shadow_missing_count": len(shadow_missing),
        "actual_missing_count": len(actual_missing),
        "decision_divergence": False,
        "shadow_progress_action": None,
        "actual_progress_action": None,
        "shadow_progress_reason": None,
        "actual_progress_reason": None,
    }

    if progress_context:
        from tools.system.tool_builder.research.progress import (
            evaluate_research_progress,
        )

        ctx = dict(progress_context)
        shadow_decision = evaluate_research_progress(
            satisfies_request=shadow.get("satisfies_request"),
            missing=shadow.get("missing"),
            previous_missing=ctx.get("previous_missing"),
            round_finding_keys=ctx.get("round_finding_keys"),
            seen_keys=ctx.get("seen_keys"),
            stagnation=ctx.get("stagnation") or 0,
            round_num=ctx.get("round_num") or 1,
            max_rounds=ctx.get("max_rounds") or 10,
            max_stagnation=ctx.get("max_stagnation") or 3,
        )
        actual_decision = evaluate_research_progress(
            satisfies_request=actual.get("satisfies_request"),
            missing=actual.get("missing"),
            previous_missing=ctx.get("previous_missing"),
            round_finding_keys=ctx.get("round_finding_keys"),
            seen_keys=ctx.get("seen_keys"),
            stagnation=ctx.get("stagnation") or 0,
            round_num=ctx.get("round_num") or 1,
            max_rounds=ctx.get("max_rounds") or 10,
            max_stagnation=ctx.get("max_stagnation") or 3,
        )
        result["shadow_progress_action"] = shadow_decision.get("action")
        result["actual_progress_action"] = actual_decision.get("action")
        result["shadow_progress_reason"] = shadow_decision.get("reason")
        result["actual_progress_reason"] = actual_decision.get("reason")
        result["decision_divergence"] = (
            shadow_decision.get("action") != actual_decision.get("action")
        )

    return result


def evaluate_global_judge_trigger(
    escalation,
    *,
    round_num,
    round_research=None,
    state=None,
    stagnation=0,
    max_rounds=10,
    max_stagnation=3,
    candidates_error=None,
):
    """Rule-based Partial の escalation 等から Global Judge 必要性を判定する。"""
    escalation = dict(escalation or {})
    round_research = round_research or {}
    triggers = []
    skip_triggers = []

    if candidates_error:
        triggers.append(TRIGGER_CANDIDATES_ERROR)
        return _result(
            needed=True,
            triggers=triggers,
            skip_triggers=skip_triggers,
            escalation=escalation,
        )

    if escalation.get("needs_partial_llm") or escalation.get("reason") == REASON_AMBIGUOUS_REF:
        triggers.append(TRIGGER_PARTIAL_LLM_UNAVAILABLE)

    if escalation.get("reason") == REASON_USABLE_GOAL:
        triggers.append(TRIGGER_USABLE_NEEDS_GOAL)

    if escalation.get("reason") == REASON_EMPTY_ROUND:
        triggers.append(TRIGGER_EMPTY_ROUND)

    if round_num <= 1:
        triggers.append(TRIGGER_FIRST_ROUND)

    if round_num >= max_rounds:
        triggers.append(TRIGGER_FINAL_ROUND)

    if stagnation >= max(0, max_stagnation - 1):
        triggers.append(TRIGGER_STAGNATION_RISK)

    usable = [
        x
        for x in (round_research.get("usable_findings") or [])
        if isinstance(x, dict)
    ]
    if usable and TRIGGER_USABLE_NEEDS_GOAL not in triggers:
        triggers.append(TRIGGER_USABLE_NEEDS_GOAL)

    routine_verify_only = (
        escalation.get("routine") is True
        and escalation.get("reason") == REASON_VERIFY_FAIL_ROUTINE
        and not usable
        and not escalation.get("needs_partial_llm")
        and escalation.get("reason") != REASON_AMBIGUOUS_REF
    )
    if routine_verify_only:
        skip_triggers.append(TRIGGER_ROUTINE_VERIFY_FAIL)

    if not triggers and not skip_triggers:
        triggers.append(TRIGGER_NON_ROUTINE_ESCALATION)

    would_skip = bool(skip_triggers) and not triggers

    if would_skip:
        needed = False
        primary_reason = REASON_VERIFY_FAIL_ROUTINE
    else:
        needed = True
        primary_reason = triggers[0] if triggers else TRIGGER_SHADOW_DEFAULT

    return _result(
        needed=needed,
        triggers=triggers,
        skip_triggers=skip_triggers,
        escalation=escalation,
        primary_reason=primary_reason,
        would_skip=would_skip,
    )


def execute_global_judge_round(
    *,
    gj_trigger,
    state,
    escalation,
    round_num,
    run_llm_judge,
    skip_event_index=0,
    progress_context=None,
):
    """
    Global Judge ラウンドを実行する。

    - shadow（既定）: would_skip でも常に LLM 呼び出し
    - live_skip（既定・通常経路）: would_skip 時 LLM 省略
      オフ: AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP=0
    - audit（既定 AUDIT_RATE=3）: N 回目の skip で LLM を呼び
      制御は live_skip judgment のまま、critical_miss / decision_divergence を計測
    """
    gj_trigger = dict(gj_trigger or {})
    escalation = escalation or {}
    live_skip = is_live_skip_enabled()
    audit_rate = get_audit_rate()
    would_skip = bool(gj_trigger.get("would_skip"))

    gj_trigger["live_skip_enabled"] = live_skip
    gj_trigger["audit_rate"] = audit_rate

    if live_skip and would_skip:
        shadow = build_shadow_judgment(state, escalation, live_skip=True)
        audit_only = should_audit_skip_event(skip_event_index, audit_rate)
        gj_trigger["mode"] = LIVE_SKIP_MODE
        gj_trigger["skip_event_index"] = skip_event_index

        if audit_only:
            gj_trigger["audit_only"] = True
            gj_trigger["live_skipped"] = False
            llm = run_llm_judge()
            actual = llm.get("judgment") or {}
            quality_compare = compare_shadow_vs_actual(
                shadow, actual, progress_context=progress_context
            )
            return {
                "judgment": shadow,
                "payload": llm.get("payload"),
                "error": llm.get("error"),
                "text": llm.get("text") or "",
                "detail": llm.get("detail"),
                "judge_held": llm.get("judge_held") or {},
                "gj_trigger": gj_trigger,
                "quality_compare": quality_compare,
                "shadow_judgment": shadow,
                "audit_judgment": actual,
                "llm_called": True,
                "live_skipped": False,
                "audit_only": True,
            }

        gj_trigger["audit_only"] = False
        gj_trigger["live_skipped"] = True
        return {
            "judgment": shadow,
            "payload": None,
            "error": None,
            "text": "",
            "detail": None,
            "judge_held": {"grade": None, "retry_ok": None, "skipped": True},
            "gj_trigger": gj_trigger,
            "quality_compare": None,
            "shadow_judgment": shadow,
            "audit_judgment": None,
            "llm_called": False,
            "live_skipped": True,
            "audit_only": False,
        }

    gj_trigger["mode"] = SHADOW_MODE if not live_skip else LIVE_SKIP_MODE
    gj_trigger["live_skipped"] = False
    gj_trigger["audit_only"] = False
    llm = run_llm_judge()
    actual = llm.get("judgment") or {}
    shadow = (
        build_shadow_judgment(state, escalation)
        if would_skip
        else None
    )
    quality_compare = (
        compare_shadow_vs_actual(
            shadow, actual, progress_context=progress_context
        )
        if shadow is not None
        else None
    )
    return {
        "judgment": actual,
        "payload": llm.get("payload"),
        "error": llm.get("error"),
        "text": llm.get("text") or "",
        "detail": llm.get("detail"),
        "judge_held": llm.get("judge_held") or {},
        "gj_trigger": gj_trigger,
        "quality_compare": quality_compare,
        "shadow_judgment": shadow,
        "audit_judgment": None,
        "llm_called": True,
        "live_skipped": False,
        "audit_only": False,
    }


def _result(
    *,
    needed,
    triggers,
    skip_triggers,
    escalation,
    primary_reason=None,
    would_skip=None,
):
    if would_skip is None:
        would_skip = not needed
    mode = LIVE_SKIP_MODE if is_live_skip_enabled() else SHADOW_MODE
    return {
        "mode": mode,
        "needed": bool(needed),
        "would_skip": bool(would_skip),
        "triggers": list(triggers or []),
        "skip_triggers": list(skip_triggers or []),
        "primary_reason": primary_reason or (triggers[0] if triggers else None),
        "escalation_reason": escalation.get("reason"),
        "escalation_routine": escalation.get("routine"),
        "llm_calls_saved_if_skip": 1 if would_skip else 0,
        "live_skip_enabled": is_live_skip_enabled(),
    }


def init_shadow_summary():
    return {
        "mode": LIVE_SKIP_MODE if is_live_skip_enabled() else SHADOW_MODE,
        "live_skip_enabled": is_live_skip_enabled(),
        "audit_rate": get_audit_rate(),
        "rounds_total": 0,
        "judge_calls_actual": 0,
        "would_skip_count": 0,
        "live_skip_count": 0,
        "audit_count": 0,
        "llm_calls_saved_estimate": 0,
        "llm_calls_saved_actual": 0,
        "quality": {
            "critical_miss_count": 0,
            "false_continue_count": 0,
            "satisfies_match_count": 0,
            "missing_match_count": 0,
            "decision_divergence_count": 0,
            "audit_compared_count": 0,
        },
        "rounds": [],
    }


def record_shadow_round(summary, round_record):
    """run 単位の shadow / live_skip 集計を更新する。"""
    summary = dict(summary or init_shadow_summary())
    summary["rounds_total"] = int(summary.get("rounds_total") or 0) + 1

    if round_record.get("llm_called"):
        summary["judge_calls_actual"] = int(summary.get("judge_calls_actual") or 0) + 1

    if round_record.get("would_skip"):
        summary["would_skip_count"] = int(summary.get("would_skip_count") or 0) + 1
        summary["llm_calls_saved_estimate"] = int(
            summary.get("llm_calls_saved_estimate") or 0
        ) + int(round_record.get("llm_calls_saved_if_skip") or 0)

    if round_record.get("live_skipped"):
        summary["live_skip_count"] = int(summary.get("live_skip_count") or 0) + 1
        summary["llm_calls_saved_actual"] = int(
            summary.get("llm_calls_saved_actual") or 0
        ) + 1

    if round_record.get("audit_only"):
        summary["audit_count"] = int(summary.get("audit_count") or 0) + 1

    quality = dict(summary.get("quality") or {})
    cmp = round_record.get("quality_compare") or {}
    if cmp:
        quality["audit_compared_count"] = int(quality.get("audit_compared_count") or 0) + 1
    if cmp.get("critical_miss"):
        quality["critical_miss_count"] = int(quality.get("critical_miss_count") or 0) + 1
    if cmp.get("false_continue"):
        quality["false_continue_count"] = int(quality.get("false_continue_count") or 0) + 1
    if cmp.get("satisfies_request_match"):
        quality["satisfies_match_count"] = int(quality.get("satisfies_match_count") or 0) + 1
    if cmp.get("missing_match"):
        quality["missing_match_count"] = int(quality.get("missing_match_count") or 0) + 1
    if cmp.get("decision_divergence"):
        quality["decision_divergence_count"] = (
            int(quality.get("decision_divergence_count") or 0) + 1
        )
    summary["quality"] = quality

    rounds = list(summary.get("rounds") or [])
    rounds.append(round_record)
    summary["rounds"] = rounds
    return summary


def finalize_observation(summary, *, rounds=None, baseline_rounds=None):
    """Phase 3.5: Judge 削減率と extra_rounds を付与する。"""
    summary = dict(summary or init_shadow_summary())
    total = int(summary.get("rounds_total") or 0)
    judge_actual = int(summary.get("judge_calls_actual") or 0)
    live_skips = int(summary.get("live_skip_count") or 0)
    would_skips = int(summary.get("would_skip_count") or 0)

    if total > 0:
        judge_reduction_rate = round(live_skips / total, 3)
        judge_call_rate = round(judge_actual / total, 3)
    else:
        judge_reduction_rate = 0.0
        judge_call_rate = 0.0

    extra_rounds = None
    if rounds is not None and baseline_rounds is not None:
        try:
            extra_rounds = int(rounds) - int(baseline_rounds)
        except (TypeError, ValueError):
            extra_rounds = None

    summary["observation"] = {
        "judge_reduction_rate": judge_reduction_rate,
        "judge_call_rate": judge_call_rate,
        "rounds": rounds,
        "baseline_rounds": baseline_rounds,
        "extra_rounds": extra_rounds,
        "would_skip_count": would_skips,
        "live_skip_count": live_skips,
        "audit_count": int(summary.get("audit_count") or 0),
        "critical_miss_count": (summary.get("quality") or {}).get("critical_miss_count", 0),
        "decision_divergence_count": (summary.get("quality") or {}).get(
            "decision_divergence_count", 0
        ),
    }
    return summary
