"""
Phase 5: Rule-based Memory Recall Policy。

History から関連度に基づき断片だけ想起し、Prompt 用 RecallBundle を返す。
LLM による記憶選択は行わない（Phase 6 Memory Judge が別途）。
"""

from __future__ import annotations

import os
from typing import Any

from tools.ai.state.retrieve import (
    count_consecutive_failures,
    event_error_class,
    event_preview,
    get_event,
    preview_events,
    retrieve_failures_for_open_questions,
)
from tools.ai.tool_builder.research_result import command_key

MODE_FRESH = "fresh"
MODE_RELATED = "related"
MODE_REPEATING = "repeating"
MODE_ESCALATION = "escalation"

REPEAT_STREAK_THRESHOLD = 2
SCORE_THRESHOLD = 2

MODE_LIMITS = {
    MODE_FRESH: 1,
    MODE_RELATED: 2,
    MODE_REPEATING: 3,
    MODE_ESCALATION: 5,
}


def memory_recall_enabled() -> bool:
    """
    Phase 5 通常経路: Recall ON。
    オフにするときだけ AI_AGENT_MEMORY_RECALL=0（旧 handoff）。
    """
    raw = os.environ.get("AI_AGENT_MEMORY_RECALL")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _open_questions(state):
    return [
        q
        for q in (getattr(state, "open_questions", None) or [])
        if isinstance(q, dict) and str(q.get("status") or "open") == "open"
    ]


def _question_ids_for_event(state, event_id):
    ids = []
    for question in _open_questions(state):
        related = list(question.get("related_events") or [])
        if event_id in related:
            ids.append(question.get("id"))
    return ids


def _event_command_key(event):
    action = event.get("action") if isinstance(event.get("action"), dict) else {}
    return (
        str((action or {}).get("command") or "").strip(),
        tuple(str(a) for a in ((action or {}).get("args") or [])),
    )


def score_event(state, event, *, current_round=None, focus_command_key=None):
    """関連度スコア。閾値未満は Recall しない。"""
    event = event or {}
    score = 0
    reasons = []
    event_id = event.get("id")
    qids = _question_ids_for_event(state, event_id)
    if qids:
        score += 4
        reasons.append("open_question_link")
    eck = _event_command_key(event)
    if focus_command_key and eck[0] and eck == focus_command_key:
        score += 3
        reasons.append("same_command_key")
    elif eck[0]:
        # 同一 command（args 違い）でも弱く加点
        for question in _open_questions(state):
            for eid in question.get("related_events") or []:
                other = get_event(getattr(state, "research_history", None), eid)
                if other and _event_command_key(other)[0] == eck[0]:
                    score += 1
                    reasons.append("same_command_name")
                    break
            if "same_command_name" in reasons:
                break
    # error_class 連続
    history = getattr(state, "research_history", None)
    streak, cls = count_consecutive_failures(history, by="error_class")
    if cls and event_error_class(event) == cls and streak >= 2:
        score += 2
        reasons.append("error_class_streak")
    round_num = (event.get("metadata") or {}).get("round")
    if current_round is not None and round_num is not None:
        try:
            delta = abs(int(current_round) - int(round_num))
        except (TypeError, ValueError):
            delta = 99
        if delta <= 1:
            score += 1
            reasons.append("recent_round")
    # 成功イベントは Candidate では通常 0（usable 側で扱う）
    if event.get("type") == "verify_ok" or (event.get("result") or {}).get("ok") is True:
        score = 0
        reasons = ["success_skipped_for_candidate"]
    return score, reasons


def decide_recall_mode(state, *, escalation=False, current_round=None):
    """規則で RecallMode を決める。"""
    if escalation:
        return MODE_ESCALATION, "global_escalation"
    history = getattr(state, "research_history", None)
    cmd_streak, cmd_key = count_consecutive_failures(history, by="command_key")
    err_streak, err_cls = count_consecutive_failures(history, by="error_class")
    if cmd_streak >= REPEAT_STREAK_THRESHOLD or err_streak >= REPEAT_STREAK_THRESHOLD:
        reason = (
            f"command_streak={cmd_streak}"
            if cmd_streak >= err_streak
            else f"error_class_streak={err_streak}:{err_cls}"
        )
        return MODE_REPEATING, reason

    fail_count = 0
    for question in _open_questions(state):
        related = list(question.get("related_events") or [])
        for eid in related:
            event = get_event(history, eid)
            if not event:
                continue
            if event.get("type") == "verify_fail" or (event.get("result") or {}).get("ok") is False:
                fail_count += 1
    if fail_count >= 2:
        return MODE_RELATED, f"open_question_fails={fail_count}"
    if fail_count <= 1:
        return MODE_FRESH, f"open_question_fails={fail_count}"
    return MODE_RELATED, "default_related"


def _candidate_failure_events(state, *, pool_limit=12):
    """スコア付け用の候補失敗イベント（新しい順・重複除去）。"""
    history = getattr(state, "research_history", None)
    collected = []
    seen = set()
    for event in retrieve_failures_for_open_questions(
        state, limit_per_question=4, total_limit=pool_limit
    ):
        eid = event.get("id")
        if eid and eid not in seen:
            seen.add(eid)
            collected.append(event)
    if history is not None:
        for event in reversed(getattr(history, "events", None) or []):
            if len(collected) >= pool_limit:
                break
            if event.get("type") != "verify_fail" and (event.get("result") or {}).get("ok") is not False:
                continue
            eid = event.get("id")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            collected.append(event)
    return collected


def select_events_for_mode(state, mode, *, current_round=None, limit=None):
    limit = limit if limit is not None else MODE_LIMITS.get(mode, 2)
    if mode == MODE_FRESH:
        limit = min(limit, 1)
    history = getattr(state, "research_history", None)
    focus_key = count_consecutive_failures(history, by="command_key")[1]
    scored = []
    omitted = []
    for event in _candidate_failure_events(state):
        score, reasons = score_event(
            state, event, current_round=current_round, focus_command_key=focus_key
        )
        if score < SCORE_THRESHOLD and mode != MODE_ESCALATION:
            # fresh は閾値を下げて最大 1 件まで許可
            if mode == MODE_FRESH and score >= 1:
                pass
            elif mode == MODE_FRESH and score == 0:
                omitted.append({"id": event.get("id"), "score": score, "reasons": reasons})
                continue
            else:
                omitted.append({"id": event.get("id"), "score": score, "reasons": reasons})
                continue
        if mode == MODE_FRESH and score < 1:
            omitted.append({"id": event.get("id"), "score": score, "reasons": reasons})
            continue
        scored.append((score, event, reasons))
    scored.sort(key=lambda item: (-item[0], -int((item[1].get("metadata") or {}).get("round") or 0)))
    selected = []
    score_trace = []
    for score, event, reasons in scored:
        if len(selected) >= limit:
            omitted.append({"id": event.get("id"), "score": score, "reasons": reasons + ["over_limit"]})
            continue
        selected.append(event)
        score_trace.append(
            {"id": event.get("id"), "score": score, "reasons": reasons}
        )
    return selected, score_trace, omitted


def banned_digest(state, *, limit=8):
    banned = getattr(state, "banned_actions", None) or []
    digest = []
    for item in banned:
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "").strip()
        if not command:
            continue
        entry = {"command": command, "args": list(item.get("args") or [])}
        reason = str(item.get("reason") or "").strip()
        if reason:
            entry["reason"] = reason[:80]
        digest.append(entry)
        if len(digest) >= limit:
            break
    return digest


def prior_failures_from_events(state, events):
    """互換キー prior_failures 用。短い narrative のみ。"""
    failures = []
    for event in events or []:
        preview = event_preview(event)
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        qtext = ""
        for question in _open_questions(state):
            if event.get("id") in (question.get("related_events") or []):
                qtext = str(question.get("text") or question.get("question") or "").strip()
                break
        if not qtext:
            cmd = str(preview.get("command") or "").strip()
            qtext = f"verify failure for {cmd}" if cmd else "verify failure"
        entry = {
            "question": qtext,
            "finding": str(preview.get("error_class") or preview.get("type") or "verify_fail"),
            "error": str(preview.get("error_preview") or "").strip(),
        }
        command = str(preview.get("command") or (action or {}).get("command") or "").strip()
        if command:
            entry["command"] = command
        args = (action or {}).get("args")
        if args:
            entry["args"] = list(args)
        failures.append(entry)
    return failures


def build_recall_bundle(
    state,
    *,
    escalation=False,
    current_round=None,
    judge_reason=None,
    recent_limit=None,
    usable_findings=None,
    previous_missing=None,
    **_kwargs,
):
    """
    Prompt 用の唯一の過去ビュー。
    policy_trace は計測用（Prompt に載せない）。
    previous_missing / **kwargs は Phase 5.1 互換のため無視。
    """
    del previous_missing
    mode, mode_reason = decide_recall_mode(
        state, escalation=escalation, current_round=current_round
    )
    limit = MODE_LIMITS.get(mode, 2)
    if recent_limit is not None:
        limit = min(limit, int(recent_limit))
    selected, score_trace, omitted = select_events_for_mode(
        state, mode, current_round=current_round, limit=limit
    )
    previews = preview_events(selected)
    judge_summary = ""
    if mode in (MODE_REPEATING, MODE_ESCALATION):
        text = str(judge_reason or "").strip()
        if text:
            judge_summary = text[:160] + ("…" if len(text) > 160 else "")
    open_qs = [
        {
            "id": q.get("id"),
            "text": q.get("text") or q.get("question"),
            "status": q.get("status") or "open",
        }
        for q in _open_questions(state)
    ]
    usable = list(usable_findings or getattr(state, "selected_findings", None) or [])
    repeating_hint = ""
    if mode == MODE_REPEATING:
        repeating_hint = (
            "Same command_key or error_class failed repeatedly. "
            "Do not repeat banned or prior_failures command/args; try a different approach."
        )
    bundle = {
        "mode": mode,
        "open_questions": open_qs,
        "usable_findings": usable[:10],
        "recalled_events": previews,
        "banned_digest": banned_digest(state),
        "judge_summary": judge_summary,
        "repeating_hint": repeating_hint,
        # 互換: Web CONTRACT が prior_failures を参照
        "prior_failures": prior_failures_from_events(state, selected),
        "policy_trace": {
            "mode_reason": mode_reason,
            "scores": score_trace,
            "omitted_ids": [item.get("id") for item in omitted],
            "omitted": omitted[:20],
            "recalled_event_count": len(previews),
            "limit": limit,
            "phase": "5",
        },
    }
    return bundle


def apply_recall_limit(bundle, *, recent_limit):
    """Phase 4 削減梯子から件数だけ落とす。mode は維持。"""
    bundle = dict(bundle or {})
    limit = max(0, int(recent_limit))
    events = list(bundle.get("recalled_events") or [])[:limit]
    failures = list(bundle.get("prior_failures") or [])[:limit]
    bundle["recalled_events"] = events
    bundle["prior_failures"] = failures
    trace = dict(bundle.get("policy_trace") or {})
    trace["recalled_event_count"] = len(events)
    trace["limit"] = limit
    trace["budget_trimmed"] = True
    bundle["policy_trace"] = trace
    return bundle


def empty_recall_bundle():
    return {
        "mode": MODE_FRESH,
        "open_questions": [],
        "usable_findings": [],
        "recalled_events": [],
        "banned_digest": [],
        "judge_summary": "",
        "repeating_hint": "",
        "prior_failures": [],
        "policy_trace": {
            "mode_reason": "empty",
            "scores": [],
            "omitted_ids": [],
            "recalled_event_count": 0,
        },
    }
