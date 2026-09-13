"""
Phase 比較用メトリクス。

最重要: 同じ原因クラス / 未解決質問 / 探索ファミリーを、
情報が増えないまま繰り返しているか。
exact command 再実行は参考指標（banned_actions 側の領域）。
"""

from __future__ import annotations

from collections import Counter

from tools.ai.state.memory_recall import (
    assess_information_gain,
    event_command_family,
)
from tools.ai.state.retrieve import event_error_class
from tools.ai.state.task_state import TaskState


def _command_key(command, args):
    return (str(command or "").strip(), tuple(str(a) for a in (args or [])))


def _fail_events(history):
    out = []
    for event in history or []:
        if event.get("type") == "verify_fail":
            out.append(event)
            continue
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        if result.get("ok") is False:
            out.append(event)
    return out


def _rate(num, den):
    if not den:
        return None
    return round(float(num) / float(den), 3)


def _repeat_rate(keys):
    """出現キーのうち、2回目以降の割合。"""
    seen = set()
    repeats = 0
    total = 0
    for key in keys:
        if key is None or key == ("", "") or key == "":
            continue
        total += 1
        if key in seen:
            repeats += 1
        seen.add(key)
    return repeats, total, _rate(repeats, total)


def missing_loop_events(judgments):
    loops = []
    prev = None
    streak = 0
    for item in judgments or []:
        missing = tuple(sorted(str(x) for x in (item.get("missing") or []) if str(x).strip()))
        if missing and missing == prev:
            streak += 1
            if streak >= 1:
                loops.append(
                    {
                        "round": item.get("round"),
                        "streak": streak + 1,
                        "missing": list(missing)[:4],
                    }
                )
        else:
            streak = 0
            prev = missing if missing else None
    return loops


def pivot_signals_from_budget(calls):
    """context_budget_shadow.calls から pivot / repeating を集計。"""
    pivot_count = 0
    repeating_calls = 0
    mode_counts = Counter()
    for item in calls or []:
        mode = item.get("recall_mode")
        if mode:
            mode_counts[mode] += 1
        if mode == "repeating":
            repeating_calls += 1
        if item.get("pivot_required"):
            pivot_count += 1
        # stuck_error_class がある呼び出しも pivot 相当（5.1）
        elif item.get("stuck_error_class") and mode == "repeating":
            pivot_count += 1
    # Phase 5: repeating_hint 相当は mode=repeating のみ
    if pivot_count == 0 and repeating_calls:
        pivot_count = repeating_calls
    return {
        "pivot_required_count": pivot_count,
        "repeating_call_count": repeating_calls,
        "recall_mode_counts": dict(mode_counts),
    }


def usable_after_pivot(rounds_detail, calls):
    """
    pivot/repeating が発生した呼び出し以降に usable が増えたか。
    rounds_detail に usable 累計が無い場合は verified_ok を代理。
    """
    pivot_rounds = set()
    for item in calls or []:
        if item.get("pivot_required") or item.get("recall_mode") == "repeating":
            rnd = item.get("round") or item.get("research_round")
            if rnd is not None:
                try:
                    pivot_rounds.add(int(rnd))
                except (TypeError, ValueError):
                    pass

    if not rounds_detail:
        return {
            "pivot_round_count": len(pivot_rounds),
            "usable_increase_after_pivot": None,
            "verify_ok_after_pivot": None,
            "note": "no_rounds_detail",
        }

    # first pivot round if any (from detail research_input hints)
    first_pivot = None
    for item in rounds_detail:
        rin = item.get("research_input") or {}
        hints = rin.get("exploration_hints") or []
        pivotish = rin.get("pivot_required") or any(
            "PIVOT REQUIRED" in str(h) or "failed repeatedly" in str(h) for h in hints
        )
        if pivotish or (item.get("round") in pivot_rounds):
            try:
                first_pivot = int(item.get("round"))
            except (TypeError, ValueError):
                first_pivot = item.get("round")
            break
    if first_pivot is None and pivot_rounds:
        first_pivot = min(pivot_rounds)

    if first_pivot is None:
        return {
            "pivot_round_count": 0,
            "usable_increase_after_pivot": False,
            "verify_ok_after_pivot": False,
            "note": "no_pivot_observed",
        }

    ok_after = 0
    for item in rounds_detail:
        try:
            rnd = int(item.get("round"))
        except (TypeError, ValueError):
            continue
        if rnd <= int(first_pivot):
            continue
        for run in item.get("verified_runs") or []:
            if run.get("ok"):
                ok_after += 1

    return {
        "pivot_round_count": 1,
        "first_pivot_round": first_pivot,
        "usable_increase_after_pivot": ok_after > 0,
        "verify_ok_after_pivot": ok_after,
        "note": "proxy_verify_ok_after_pivot",
    }


def no_gain_loop_from_history(history, judgments=None, state_snapshot=None):
    """
    オフライン近似: 終端時点の assess_information_gain + missing ループ。
    """
    from tools.ai.state.research_history import ResearchHistory

    history_list = list(history or [])
    open_questions = []
    selected_findings = []
    if isinstance(state_snapshot, dict):
        open_questions = list(state_snapshot.get("open_questions") or [])
        selected_findings = list(state_snapshot.get("selected_findings") or [])
    state = TaskState(
        open_questions=open_questions,
        selected_findings=selected_findings,
        research_history=ResearchHistory.from_snapshot(history_list),
    )
    info = assess_information_gain(state)
    loops = missing_loop_events(judgments)
    no_gain = bool(info.get("no_gain"))
    loop_rate = _rate(len(loops), max(len(judgments or []), 1))
    return {
        "no_gain": no_gain,
        "no_gain_loop_rate": loop_rate if (no_gain or loops) else 0.0,
        "information_gain": {
            "has_gain": info.get("has_gain"),
            "no_gain": info.get("no_gain"),
            "reasons_gain": info.get("reasons_gain"),
            "reasons_stuck": info.get("reasons_stuck"),
            "stuck_error_class": info.get("stuck_error_class"),
            "stuck_family": list(info.get("stuck_family") or []) or None,
        },
        "missing_loop_events": len(loops),
        "missing_loops": loops[-5:],
    }


def compute_compare_metrics(run):
    """1 run（research_implement 保存形式）から比較指標を算出。"""
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    cb = pipe.get("context_budget_shadow") or {}
    cb_summary = cb.get("summary") or {}
    calls = cb.get("calls") or []
    history = pipe.get("research_history") or []
    judgments = pipe.get("judgments") or []
    rounds_detail = pipe.get("research_rounds_detail") or []
    state_snap = run.get("state")

    fails = _fail_events(history)
    cmd_keys = []
    class_keys = []
    family_keys = []
    for event in fails:
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        key = _command_key((action or {}).get("command"), (action or {}).get("args"))
        if key[0]:
            cmd_keys.append(key)
        cls = event_error_class(event)
        if cls:
            class_keys.append(cls)
        fam = event_command_family(event)
        if fam != ("", ""):
            family_keys.append(fam)

    cmd_rep, cmd_tot, cmd_rate = _repeat_rate(cmd_keys)
    cls_rep, cls_tot, cls_rate = _repeat_rate(class_keys)
    fam_rep, fam_tot, fam_rate = _repeat_rate(family_keys)

    # open_question: judgments missing loops / judgment count
    loops = missing_loop_events(judgments)
    oq_rate = _rate(len(loops), max(len(judgments), 1))

    gain = no_gain_loop_from_history(history, judgments, state_snap)
    pivots = pivot_signals_from_budget(calls)
    after = usable_after_pivot(rounds_detail, calls)

    overflow = any(t.get("error") == "context_overflow" for t in trace) or (
        run.get("error") == "context_overflow"
    )

    # primary waste score: no-gain class/family/oq recurrence
    waste_events = 0
    if gain.get("no_gain"):
        waste_events += cls_rep + fam_rep + len(loops)

    return {
        "pass": run.get("pass"),
        "result": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "stop_reason": research.get("stop_reason"),
        "rounds": research.get("rounds"),
        "llm_calls": timing.get("llm_calls"),
        "usable_findings": len(research.get("usable_findings") or []),
        "insufficient_findings": len(research.get("insufficient_findings") or []),
        "verify_fail_count": len(fails),
        "repeat_same_command_rate": cmd_rate,
        "repeat_same_command_count": cmd_rep,
        "repeat_same_error_class_rate": cls_rate,
        "repeat_same_error_class_count": cls_rep,
        "repeat_same_command_family_rate": fam_rate,
        "repeat_same_command_family_count": fam_rep,
        "repeated_open_question_rate": oq_rate,
        "repeated_open_question_count": len(loops),
        "no_gain": gain.get("no_gain"),
        "no_gain_loop_rate": gain.get("no_gain_loop_rate"),
        "information_gain": gain.get("information_gain"),
        "pivot_required_count": pivots.get("pivot_required_count"),
        "repeating_call_count": pivots.get("repeating_call_count"),
        "recall_mode_counts": pivots.get("recall_mode_counts"),
        "usable_increase_after_pivot": after.get("usable_increase_after_pivot"),
        "verify_ok_after_pivot": after.get("verify_ok_after_pivot"),
        "pivot_followup": after,
        "actual_headroom_min": cb_summary.get("actual_headroom_min"),
        "headroom_gate_ok": cb_summary.get("headroom_gate_ok"),
        "allocated_chars_max": cb_summary.get("allocated_chars_max"),
        "reduction_applied_count": cb_summary.get("reduction_applied_count"),
        "defer_count": cb_summary.get("defer_count"),
        "context_overflow": overflow,
        "history_event_count": len(history),
        "primary_waste_event_count": waste_events,
        "eval_focus": (
            "no_gain_error_class_family_open_question_loop"
        ),
    }
