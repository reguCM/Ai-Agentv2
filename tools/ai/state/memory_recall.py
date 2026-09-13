"""
Phase 5 / 5.1: Rule-based Memory Recall Policy。

介入対象（分析に基づく）:
  - 同じ error_class の連続（command が変わっても）
  - 同じ open_question / missing ループ
  - 同じ command_family の再探索
  - 情報が増えていない停滞

非対象:
  - exact command_key 再実行 → banned_actions / filter_rejected に委譲
  - prior_failures の単純増量はしない。repeating は pivot 促進が目的。
"""

from __future__ import annotations

import os
import re
from typing import Any

from tools.ai.state.retrieve import (
    count_consecutive_failures,
    event_error_class,
    event_preview,
    get_event,
    preview_events,
    retrieve_failures_for_open_questions,
)

MODE_FRESH = "fresh"
MODE_RELATED = "related"
MODE_REPEATING = "repeating"
MODE_ESCALATION = "escalation"

# error_class / family / missing-loop 用。exact command_key は使わない。
REPEAT_STREAK_THRESHOLD = 2
SCORE_THRESHOLD = 2
MISSING_LOOP_MIN_FAILS = 2

MODE_LIMITS = {
    MODE_FRESH: 1,
    MODE_RELATED: 2,
    # repeating: 代表例のみ（増量しない）
    MODE_REPEATING: 2,
    MODE_ESCALATION: 5,
}

_FAMILY_TOKEN_RE = re.compile(
    r"Win32_\w+|Get-\w+|nvidia-smi|wmic|ciminstance|cim|"
    r"temperature|memory|disk|vram|gpu|cpu|LoadPercentage|"
    r"FreePhysicalMemory|TotalPhysicalMemory",
    re.I,
)


def memory_recall_enabled() -> bool:
    """
    Phase 5 通常経路: Recall ON。
    オフにするときだけ AI_AGENT_MEMORY_RECALL=0（旧 handoff）。
    """
    raw = os.environ.get("AI_AGENT_MEMORY_RECALL")
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def memory_recall_policy_version() -> str:
    """
    Recall Policy の版。
    - \"5\" / phase5: 旧 Rule-based（command_key / error_class streak）
    - \"5.1\"（既定）: error_class / family / open_question + no_gain pivot
    MEMORY_RECALL=0 のときは参照されない（Phase 4 live）。
    """
    raw = os.environ.get("AI_AGENT_MEMORY_RECALL_VERSION")
    if raw is None or str(raw).strip() == "":
        return "5.1"
    text = str(raw).strip().lower()
    if text in ("5", "phase5", "v5", "legacy"):
        return "5"
    return "5.1"


def _legacy_v5_module():
    from tools.ai.state import memory_recall_v5 as module

    return module


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


def command_family(action_or_event):
    """
    類似目的の探索ファミリー。
    exact args ではなく command + 主トークン（Win32_* / Get-* 等）。
    """
    if isinstance(action_or_event, dict) and "action" in action_or_event:
        action = action_or_event.get("action") or {}
    else:
        action = action_or_event or {}
    if not isinstance(action, dict):
        action = {}
    cmd = str(action.get("command") or "").strip().lower()
    args = " ".join(str(a) for a in (action.get("args") or []))
    tokens = [t.lower() for t in _FAMILY_TOKEN_RE.findall(args)]
    # Win32_* / 計測対象語を Get-* より優先（同じクラスを別 cmdlet で叩くのを同一 family とみなす）
    token = ""
    for t in tokens:
        if t.startswith("win32_"):
            token = t
            break
    if not token:
        for preferred in (
            "temperature",
            "memory",
            "disk",
            "vram",
            "gpu",
            "cpu",
            "loadpercentage",
            "freephysicalmemory",
            "totalphysicalmemory",
            "nvidia-smi",
            "wmic",
            "ciminstance",
            "cim",
        ):
            for t in tokens:
                if t == preferred or t.startswith(preferred):
                    token = t
                    break
            if token:
                break
    if not token and tokens:
        token = tokens[0]
    if not cmd and not token:
        return ("", "")
    return (cmd or "_", token or "_")


def event_command_family(event):
    return command_family(event)


def _is_fail_event(event):
    if not event:
        return False
    if event.get("type") == "verify_fail":
        return True
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    return result.get("ok") is False


def _is_ok_event(event):
    if not event:
        return False
    if event.get("type") == "verify_ok":
        return True
    result = event.get("result") if isinstance(event.get("result"), dict) else {}
    return result.get("ok") is True


def _recent_fail_events(history, *, limit=8):
    fails = []
    if history is None:
        return fails
    for event in reversed(getattr(history, "events", None) or []):
        if not _is_fail_event(event):
            if _is_ok_event(event):
                break
            continue
        fails.append(event)
        if len(fails) >= limit:
            break
    return fails


def count_family_streak(history, *, n_lookback=8):
    """直近失敗の同一 command_family 連続数。"""
    fails = _recent_fail_events(history, limit=n_lookback)
    if not fails:
        return 0, None
    first = event_command_family(fails[0])
    if first == ("", ""):
        return 0, None
    streak = 0
    for event in fails:
        if event_command_family(event) != first:
            break
        streak += 1
    return streak, first


def open_question_fail_counts(state):
    """未解決 open_question ごとの関連 fail 件数。"""
    history = getattr(state, "research_history", None)
    counts = []
    for question in _open_questions(state):
        n = 0
        for eid in question.get("related_events") or []:
            event = get_event(history, eid)
            if event and _is_fail_event(event):
                n += 1
        counts.append(
            {
                "id": question.get("id"),
                "text": question.get("text") or question.get("question"),
                "fail_count": n,
            }
        )
    return counts


def assess_information_gain(state, *, lookback_fails=4):
    """
    直近の失敗区間で「新しい情報が増えたか」を規則判定する。

    増加ありの例: verify_ok、新しい error_class、新しい family、open_question 解決。
    増加なし: 同 error_class / 同 family の失敗が続き、usable が増えていない。
    """
    history = getattr(state, "research_history", None)
    events = list(getattr(history, "events", None) or [])
    reasons_gain = []
    reasons_stuck = []

    recent_slice = events[-(lookback_fails * 3) :] if events else []
    if any(_is_ok_event(e) for e in recent_slice):
        reasons_gain.append("recent_verify_ok")

    selected = getattr(state, "selected_findings", None) or []
    if selected:
        reasons_gain.append("has_usable_selected")

    fails = _recent_fail_events(history, limit=lookback_fails)
    classes = [event_error_class(e) for e in fails]
    families = [event_command_family(e) for e in fails if event_command_family(e) != ("", "")]
    unique_classes = {c for c in classes if c}
    unique_families = set(families)

    if len(unique_classes) >= 2:
        reasons_gain.append("diverse_error_classes")
    if len(unique_families) >= 2:
        reasons_gain.append("diverse_command_families")

    stuck_error_class = None
    stuck_family = None
    if len(fails) >= REPEAT_STREAK_THRESHOLD:
        if len(unique_classes) == 1:
            stuck_error_class = next(iter(unique_classes))
            reasons_stuck.append(f"same_error_class:{stuck_error_class}")
        if len(unique_families) == 1 and unique_families:
            stuck_family = next(iter(unique_families))
            reasons_stuck.append(
                f"same_command_family:{stuck_family[0]}/{stuck_family[1]}"
            )

    q_counts = open_question_fail_counts(state)
    looping_questions = [
        q for q in q_counts if q.get("fail_count", 0) >= MISSING_LOOP_MIN_FAILS
    ]
    if looping_questions and not reasons_gain:
        reasons_stuck.append("open_question_loop")

    # 情報増加: gain 理由があり、かつ「単一クラス停滞」だけではない
    has_gain = bool(reasons_gain) and not (
        stuck_error_class and len(fails) >= REPEAT_STREAK_THRESHOLD and not any(
            r.startswith("recent_verify_ok") or r == "has_usable_selected"
            for r in reasons_gain
        )
    )
    # より明確: verify_ok / usable があれば常に gain。多様性だけの場合は stuck と両立しうるので
    # 「停滞判定用の no_gain」は stuck 理由があり gain の強い信号が無いこと。
    strong_gain = any(
        r in ("recent_verify_ok", "has_usable_selected") for r in reasons_gain
    )
    no_gain = (not strong_gain) and bool(reasons_stuck)

    return {
        "has_gain": strong_gain or (bool(reasons_gain) and not reasons_stuck),
        "no_gain": no_gain,
        "reasons_gain": reasons_gain,
        "reasons_stuck": reasons_stuck,
        "stuck_error_class": stuck_error_class,
        "stuck_family": stuck_family,
        "looping_questions": looping_questions,
        "recent_fail_count": len(fails),
    }


def score_event(state, event, *, current_round=None, focus_error_class=None, focus_family=None):
    """関連度スコア。error_class / open_question / family を優先。exact key は加点しない。"""
    event = event or {}
    score = 0
    reasons = []
    event_id = event.get("id")
    qids = _question_ids_for_event(state, event_id)
    if qids:
        score += 4
        reasons.append("open_question_link")
    cls = event_error_class(event)
    if focus_error_class and cls == focus_error_class:
        score += 3
        reasons.append("same_error_class")
    fam = event_command_family(event)
    if focus_family and fam != ("", "") and fam == focus_family:
        score += 3
        reasons.append("same_command_family")
    round_num = (event.get("metadata") or {}).get("round")
    if current_round is not None and round_num is not None:
        try:
            delta = abs(int(current_round) - int(round_num))
        except (TypeError, ValueError):
            delta = 99
        if delta <= 1:
            score += 1
            reasons.append("recent_round")
    if _is_ok_event(event):
        score = 0
        reasons = ["success_skipped_for_candidate"]
    return score, reasons


def decide_recall_mode(state, *, escalation=False, current_round=None, previous_missing=None):
    """
    Phase 5.1: repeating は error_class / family / open_question ループ + 情報非増加。
    exact command_key 連続は主判定に使わない。
    """
    if memory_recall_policy_version() == "5":
        return _legacy_v5_module().decide_recall_mode(
            state, escalation=escalation, current_round=current_round
        )
    if escalation:
        return MODE_ESCALATION, "global_escalation"

    history = getattr(state, "research_history", None)
    info = assess_information_gain(state)
    err_streak, err_cls = count_consecutive_failures(history, by="error_class")
    fam_streak, fam_key = count_family_streak(history)

    missing_loop = False
    if previous_missing:
        # 呼び出し側が同じ missing を渡した場合
        missing_loop = True
    looping = info.get("looping_questions") or []
    if looping and info.get("no_gain"):
        missing_loop = True

    repeating_triggers = []
    if info.get("no_gain"):
        if err_streak >= REPEAT_STREAK_THRESHOLD:
            repeating_triggers.append(f"error_class_streak={err_streak}:{err_cls}")
        if fam_streak >= REPEAT_STREAK_THRESHOLD:
            repeating_triggers.append(
                f"family_streak={fam_streak}:{fam_key[0] if fam_key else ''}/"
                f"{fam_key[1] if fam_key else ''}"
            )
        if missing_loop:
            repeating_triggers.append(
                "open_question_loop="
                + ",".join(str(q.get("id")) for q in looping[:3])
            )

    if repeating_triggers:
        return MODE_REPEATING, ";".join(repeating_triggers) + ";no_information_gain"

    fail_count = sum(q.get("fail_count") or 0 for q in open_question_fail_counts(state))
    if fail_count >= 2:
        return MODE_RELATED, f"open_question_fails={fail_count}"
    if fail_count <= 1:
        return MODE_FRESH, f"open_question_fails={fail_count}"
    return MODE_RELATED, "default_related"


def _candidate_failure_events(state, *, pool_limit=12):
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
            if not _is_fail_event(event):
                continue
            eid = event.get("id")
            if not eid or eid in seen:
                continue
            # command 空の empty_sample は Prompt ノイズになりやすいので候補から薄くする
            action = event.get("action") if isinstance(event.get("action"), dict) else {}
            if not str((action or {}).get("command") or "").strip():
                continue
            seen.add(eid)
            collected.append(event)
    return collected


def select_events_for_mode(state, mode, *, current_round=None, limit=None, info=None):
    limit = limit if limit is not None else MODE_LIMITS.get(mode, 2)
    if mode == MODE_FRESH:
        limit = min(limit, 1)
    if mode == MODE_REPEATING:
        # 増量しない。代表 1〜2
        limit = min(limit, 2)
    info = info or assess_information_gain(state)
    focus_cls = info.get("stuck_error_class")
    focus_fam = info.get("stuck_family")
    if not focus_cls:
        focus_cls = count_consecutive_failures(
            getattr(state, "research_history", None), by="error_class"
        )[1]
    if not focus_fam:
        focus_fam = count_family_streak(getattr(state, "research_history", None))[1]

    scored = []
    omitted = []
    for event in _candidate_failure_events(state):
        score, reasons = score_event(
            state,
            event,
            current_round=current_round,
            focus_error_class=focus_cls,
            focus_family=focus_fam,
        )
        if mode == MODE_REPEATING:
            # repeating: 停滞クラス/ファミリーの代表だけ残す
            cls = event_error_class(event)
            fam = event_command_family(event)
            if focus_cls and cls != focus_cls and focus_fam and fam != focus_fam:
                omitted.append(
                    {
                        "id": event.get("id"),
                        "score": score,
                        "reasons": reasons + ["not_stuck_pattern"],
                    }
                )
                continue
        if score < SCORE_THRESHOLD and mode != MODE_ESCALATION:
            if mode == MODE_FRESH and score >= 1:
                pass
            else:
                omitted.append({"id": event.get("id"), "score": score, "reasons": reasons})
                continue
        if mode == MODE_FRESH and score < 1:
            omitted.append({"id": event.get("id"), "score": score, "reasons": reasons})
            continue
        scored.append((score, event, reasons))

    scored.sort(
        key=lambda item: (
            -item[0],
            -int((item[1].get("metadata") or {}).get("round") or 0),
        )
    )

    # repeating: 可能なら異なる command の同クラス例を優先（「変えても同じ」を示す）
    selected = []
    score_trace = []
    seen_commands = set()
    if mode == MODE_REPEATING:
        for score, event, reasons in scored:
            cmd = _event_command_key(event)[0]
            if cmd and cmd in seen_commands and len(selected) >= 1:
                continue
            if len(selected) >= limit:
                omitted.append(
                    {
                        "id": event.get("id"),
                        "score": score,
                        "reasons": reasons + ["over_limit"],
                    }
                )
                continue
            selected.append(event)
            if cmd:
                seen_commands.add(cmd)
            score_trace.append({"id": event.get("id"), "score": score, "reasons": reasons})
    else:
        for score, event, reasons in scored:
            if len(selected) >= limit:
                omitted.append(
                    {
                        "id": event.get("id"),
                        "score": score,
                        "reasons": reasons + ["over_limit"],
                    }
                )
                continue
            selected.append(event)
            score_trace.append({"id": event.get("id"), "score": score, "reasons": reasons})
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
    """互換キー prior_failures。短い narrative のみ（増量しない）。"""
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
        fam = event_command_family(event)
        entry = {
            "question": qtext,
            "finding": str(preview.get("error_class") or preview.get("type") or "verify_fail"),
            "error": str(preview.get("error_preview") or "").strip(),
            "error_class": preview.get("error_class"),
            "command_family": list(fam) if fam != ("", "") else [],
        }
        command = str(preview.get("command") or (action or {}).get("command") or "").strip()
        if command:
            entry["command"] = command
        args = (action or {}).get("args")
        if args:
            entry["args"] = list(args)
        failures.append(entry)
    return failures


def build_pivot_hint(info, *, open_questions=None):
    """repeating 用。失敗リスト増量ではなく pivot を促す短文。"""
    parts = ["PIVOT REQUIRED."]
    cls = info.get("stuck_error_class")
    if cls:
        parts.append(
            f"Stuck on error_class={cls}. Changing syntax in the same family is not enough."
        )
    fam = info.get("stuck_family")
    if fam:
        parts.append(
            f"Avoid command_family {fam[0]}/{fam[1]}; pick a different measurement route."
        )
    looping = info.get("looping_questions") or []
    if looping:
        texts = [str(q.get("text") or q.get("id") or "")[:60] for q in looping[:2]]
        parts.append(
            "Open questions unchanged despite retries: " + "; ".join(texts) + "."
        )
    parts.append(
        "Do not repeat banned_actions. Propose a fundamentally different approach."
    )
    return " ".join(parts)


def build_recall_bundle(
    state,
    *,
    escalation=False,
    current_round=None,
    judge_reason=None,
    recent_limit=None,
    usable_findings=None,
    previous_missing=None,
):
    """
    Prompt 用の過去ビュー。
    repeating でも prior_failures は代表例のみ。本体は pivot hint。
    """
    if memory_recall_policy_version() == "5":
        return _legacy_v5_module().build_recall_bundle(
            state,
            escalation=escalation,
            current_round=current_round,
            judge_reason=judge_reason,
            recent_limit=recent_limit,
            usable_findings=usable_findings,
            previous_missing=previous_missing,
        )
    info = assess_information_gain(state)
    mode, mode_reason = decide_recall_mode(
        state,
        escalation=escalation,
        current_round=current_round,
        previous_missing=previous_missing,
    )
    limit = MODE_LIMITS.get(mode, 2)
    if recent_limit is not None:
        limit = min(limit, int(recent_limit))
    selected, score_trace, omitted = select_events_for_mode(
        state, mode, current_round=current_round, limit=limit, info=info
    )
    previews = preview_events(selected)
    judge_summary = ""
    if mode in (MODE_REPEATING, MODE_ESCALATION):
        text = str(judge_reason or "").strip()
        if text:
            judge_summary = text[:120] + ("…" if len(text) > 120 else "")
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
    pivot_required = False
    if mode == MODE_REPEATING:
        pivot_required = True
        repeating_hint = build_pivot_hint(info, open_questions=open_qs)

    # repeating: prior_failures は最大 2（増量禁止）。fresh は 0〜1
    prior = prior_failures_from_events(state, selected)
    if mode == MODE_REPEATING:
        prior = prior[:2]
    elif mode == MODE_FRESH:
        prior = prior[:1]

    bundle = {
        "mode": mode,
        "open_questions": open_qs,
        "usable_findings": usable[:10],
        "recalled_events": previews,
        "banned_digest": banned_digest(state),
        "judge_summary": judge_summary,
        "repeating_hint": repeating_hint,
        "pivot_required": pivot_required,
        "stuck_error_class": info.get("stuck_error_class"),
        "stuck_family": list(info.get("stuck_family") or []) or None,
        "information_gain": {
            "has_gain": info.get("has_gain"),
            "no_gain": info.get("no_gain"),
            "reasons_gain": info.get("reasons_gain"),
            "reasons_stuck": info.get("reasons_stuck"),
        },
        # 互換キー（件数は mode に応じて抑制済み）
        "prior_failures": prior,
        "policy_trace": {
            "mode_reason": mode_reason,
            "scores": score_trace,
            "omitted_ids": [item.get("id") for item in omitted],
            "omitted": omitted[:20],
            "recalled_event_count": len(previews),
            "prior_failures_count": len(prior),
            "limit": limit,
            "phase": "5.1",
        },
    }
    return bundle


def apply_recall_limit(bundle, *, recent_limit):
    """Phase 4 削減梯子から件数だけ落とす。mode / pivot hint は維持。"""
    if memory_recall_policy_version() == "5":
        return _legacy_v5_module().apply_recall_limit(bundle, recent_limit=recent_limit)
    bundle = dict(bundle or {})
    limit = max(0, int(recent_limit))
    if bundle.get("mode") == MODE_REPEATING:
        limit = min(limit, 2)
    events = list(bundle.get("recalled_events") or [])[:limit]
    failures = list(bundle.get("prior_failures") or [])[:limit]
    bundle["recalled_events"] = events
    bundle["prior_failures"] = failures
    trace = dict(bundle.get("policy_trace") or {})
    trace["recalled_event_count"] = len(events)
    trace["prior_failures_count"] = len(failures)
    trace["limit"] = limit
    trace["budget_trimmed"] = True
    bundle["policy_trace"] = trace
    return bundle


def empty_recall_bundle():
    if memory_recall_policy_version() == "5":
        return _legacy_v5_module().empty_recall_bundle()
    return {
        "mode": MODE_FRESH,
        "open_questions": [],
        "usable_findings": [],
        "recalled_events": [],
        "banned_digest": [],
        "judge_summary": "",
        "repeating_hint": "",
        "pivot_required": False,
        "stuck_error_class": None,
        "stuck_family": None,
        "information_gain": {},
        "prior_failures": [],
        "policy_trace": {
            "mode_reason": "empty",
            "scores": [],
            "omitted_ids": [],
            "recalled_event_count": 0,
            "phase": "5.1",
        },
    }
