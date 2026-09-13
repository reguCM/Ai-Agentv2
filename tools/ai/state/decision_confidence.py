"""
KSS-1: Decision Observability / Confidence Calibration（観測のみ）。

LLM の自己評価 confidence と実 outcome を provenance 付きで対応付ける。
行動・filtering・routing は一切変更しない。

Env: AI_AGENT_KSS1_OBS=1 で観測 ON（既定 OFF）。
"""

from __future__ import annotations

import os
import uuid
from collections import defaultdict

from tools.ai.state.memory_recall import (
    assess_information_gain,
    command_family,
    event_command_family,
)
from tools.ai.state.retrieve import classify_error_class, event_error_class

CONFIDENCE_KEYS = (
    "problem_confidence",
    "solution_confidence",
    "source_confidence",
    "action_confidence",
    "expected_information_gain",
)

PREFERRED_SOURCES = (
    "history",
    "state",
    "local_llm",
    "external_research",
    "higher_llm",
    "human_help",
    "unknown",
)

OUTCOME_SUCCESS = "success"
OUTCOME_USEFUL_FAILURE = "useful_failure"
OUTCOME_ZERO_INFO = "zero_information_failure"

HIGH_CONFIDENCE_THRESHOLD = 0.8


def kss1_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS1_OBS")
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _clamp01(value):
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return max(0.0, min(1.0, v))


def _new_decision_id():
    return f"decision_{uuid.uuid4().hex[:12]}"


def empty_confidence_block():
    return {key: None for key in CONFIDENCE_KEYS}


def parse_confidence_fields(raw):
    """dict から confidence 5項目を読む。欠落は None（0 にしない）。"""
    raw = raw if isinstance(raw, dict) else {}
    out = empty_confidence_block()
    for key in CONFIDENCE_KEYS:
        if key in raw and raw.get(key) is not None:
            out[key] = _clamp01(raw.get(key))
    return out


def parse_preferred_source(raw):
    raw = raw if isinstance(raw, dict) else {}
    src = str(raw.get("preferred_source") or "").strip().lower()
    if src in PREFERRED_SOURCES:
        return src
    if src:
        return "unknown"
    return None


def extract_payload_observation(payload):
    """
    LLM JSON から optional observation を抽出。
    トップレベル observation または各 candidate 内 observation / 直置きフィールド。
    """
    payload = payload if isinstance(payload, dict) else {}
    top = payload.get("observation")
    top_conf = parse_confidence_fields(top if isinstance(top, dict) else {})
    top_source = parse_preferred_source(top if isinstance(top, dict) else {})
    if isinstance(top, dict) and top.get("preferred_source") and not top_source:
        top_source = "unknown"

    per_candidate = []
    for idx, cand in enumerate(payload.get("candidates") or []):
        if not isinstance(cand, dict):
            per_candidate.append(None)
            continue
        nested = cand.get("observation") if isinstance(cand.get("observation"), dict) else {}
        merged = {}
        merged.update(top_conf)
        merged.update({k: nested.get(k) for k in CONFIDENCE_KEYS if nested.get(k) is not None})
        # candidate 直置き
        direct = parse_confidence_fields(cand)
        for k, v in direct.items():
            if v is not None:
                merged[k] = v
        # fill from top if still None
        for k in CONFIDENCE_KEYS:
            if merged.get(k) is None:
                merged[k] = top_conf.get(k)
        pref = (
            parse_preferred_source(nested)
            or parse_preferred_source(cand)
            or top_source
        )
        per_candidate.append(
            {
                "candidate_index": idx,
                **{k: merged.get(k) for k in CONFIDENCE_KEYS},
                "preferred_source": pref,
                "observation_present": any(
                    merged.get(k) is not None for k in CONFIDENCE_KEYS
                )
                or pref is not None,
            }
        )
    return {
        "round_observation": {
            **top_conf,
            "preferred_source": top_source,
            "observation_present": any(v is not None for v in top_conf.values())
            or top_source is not None,
        },
        "per_candidate": per_candidate,
    }


def strip_observation_fields(candidates):
    """
    verifier に渡す前に観測フィールドを剥がす（行動同一のため）。
    元リストは変更せず新リストを返す。
    """
    cleaned = []
    drop_keys = set(CONFIDENCE_KEYS) | {
        "observation",
        "preferred_source",
        "decision_id",
        "expected_success",
        "predicted_success",
    }
    for cand in candidates or []:
        if not isinstance(cand, dict):
            continue
        cleaned.append({k: v for k, v in cand.items() if k not in drop_keys})
    return cleaned


def attach_decisions(candidates, extracted, *, round_num=None):
    """候補ごとに decision_id と confidence 観測を付与（実行用候補とは別構造）。"""
    decisions = []
    per = list(extracted.get("per_candidate") or [])
    round_obs = extracted.get("round_observation") or {}
    for idx, cand in enumerate(candidates or []):
        if not isinstance(cand, dict):
            continue
        obs = per[idx] if idx < len(per) and per[idx] else None
        if not obs:
            obs = {
                "candidate_index": idx,
                **empty_confidence_block(),
                "preferred_source": round_obs.get("preferred_source"),
                "observation_present": False,
            }
        decision_id = _new_decision_id()
        decisions.append(
            {
                "decision_id": decision_id,
                "round": round_num,
                "proposal_id": f"cand_{idx}",
                "action": {
                    "command": cand.get("command"),
                    "args": list(cand.get("args") or []),
                    "question": cand.get("question"),
                    "route": cand.get("route"),
                },
                "problem_confidence": obs.get("problem_confidence"),
                "solution_confidence": obs.get("solution_confidence"),
                "source_confidence": obs.get("source_confidence"),
                "action_confidence": obs.get("action_confidence"),
                "expected_information_gain": obs.get("expected_information_gain"),
                "expected_success": None,  # 後段用。現段階では未取得可
                "preferred_source": obs.get("preferred_source"),
                "observation_present": bool(obs.get("observation_present")),
                "not_for_decision": True,
                "phase": "kss-1",
            }
        )
    return decisions


def _command_key(command, args):
    return (str(command or "").strip(), tuple(str(a) for a in (args or [])))


def classify_outcome(
    *,
    actual_success,
    coverage_before=None,
    coverage_after=None,
    error_class=None,
    error_class_before=None,
    open_question_changed=None,
):
    """
    success / useful_failure / zero_information_failure。
    no_gain は coverage 経由（memory_recall.assess_information_gain）を利用。
    """
    if actual_success:
        return {
            "outcome_class": OUTCOME_SUCCESS,
            "actual_success": True,
            "actual_useful_failure": False,
            "actual_no_gain": False,
            "actual_information_gain": True,
        }

    before = coverage_before or {}
    after = coverage_after or {}
    no_gain_after = after.get("no_gain")
    if no_gain_after is None:
        no_gain_after = before.get("no_gain")

    useful_signals = []
    if before.get("no_gain") and after.get("no_gain") is False:
        useful_signals.append("escaped_no_gain")
    if (after.get("has_usable_in_state") and not before.get("has_usable_in_state")):
        useful_signals.append("usable_appeared")
    if (
        error_class
        and error_class_before
        and error_class != error_class_before
        and error_class not in (None, "other")
    ):
        useful_signals.append("new_error_class")
    if open_question_changed:
        useful_signals.append("open_question_changed")
    if after.get("information_gain", {}).get("has_gain") and not before.get(
        "information_gain", {}
    ).get("has_gain"):
        useful_signals.append("information_gain_flag")

    if useful_signals:
        return {
            "outcome_class": OUTCOME_USEFUL_FAILURE,
            "actual_success": False,
            "actual_useful_failure": True,
            "actual_no_gain": False,
            "actual_information_gain": True,
            "useful_signals": useful_signals,
        }

    # zero information: fail + no_gain（既存判定を再利用）
    zero = bool(no_gain_after) or (
        before.get("no_gain") is True and after.get("no_gain") is not False
    )
    return {
        "outcome_class": OUTCOME_ZERO_INFO if zero else OUTCOME_USEFUL_FAILURE,
        "actual_success": False,
        "actual_useful_failure": not zero,
        "actual_no_gain": bool(zero),
        "actual_information_gain": not zero,
        "useful_signals": [] if zero else ["ambiguous_fail_treated_useful"],
    }


def link_decisions_to_results(
    decisions,
    verified_results,
    *,
    coverage_before=None,
    coverage_after=None,
    history_event_ids=None,
    stuck_error_class_before=None,
):
    """decision_id ↔ verify result を command/args で接続。"""
    by_key = {}
    for item in verified_results or []:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        key = _command_key((evidence or {}).get("command"), (evidence or {}).get("args"))
        if key[0]:
            by_key[key] = item

    linked = []
    for dec in decisions or []:
        action = dec.get("action") or {}
        key = _command_key(action.get("command"), action.get("args"))
        result = by_key.get(key)
        ok = False
        error_class = None
        result_id = None
        fam = command_family(action)
        if result:
            ok = result.get("confidence") == "high"
            result_id = result.get("id") or f"result_{key[0]}"
            err = str((result.get("evidence") or {}).get("error") or "")
            if not ok:
                error_class = classify_error_class(err)
        outcome = classify_outcome(
            actual_success=ok,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            error_class=error_class,
            error_class_before=stuck_error_class_before,
        )
        hist_id = None
        if history_event_ids and isinstance(history_event_ids, dict):
            hist_id = history_event_ids.get(key)
        linked.append(
            {
                **dec,
                "result_id": result_id,
                "history_event_id": hist_id,
                "result_linked": result is not None,
                "error_class": error_class,
                "command_family": list(fam) if fam != ("", "") else [],
                **outcome,
                "high_confidence_zero_gain": bool(
                    (dec.get("action_confidence") is not None)
                    and dec.get("action_confidence") >= HIGH_CONFIDENCE_THRESHOLD
                    and outcome.get("actual_no_gain")
                ),
                "high_confidence_failure": bool(
                    (dec.get("action_confidence") is not None)
                    and dec.get("action_confidence") >= HIGH_CONFIDENCE_THRESHOLD
                    and not ok
                ),
            }
        )
    return linked


def detect_high_confidence_stuck(linked_decisions_by_round):
    """
    高 confidence のまま同一 error_class 等で no_gain が続くパターン。
    linked_decisions_by_round: [{round, decisions:[...]}, ...]
    """
    streak = 0
    prev_cls = None
    confidences = []
    events = []
    for block in linked_decisions_by_round or []:
        rnd = block.get("round")
        for dec in block.get("decisions") or []:
            ac = dec.get("action_confidence")
            if ac is None or ac < HIGH_CONFIDENCE_THRESHOLD:
                streak = 0
                prev_cls = None
                confidences = []
                continue
            if not dec.get("actual_no_gain") and not dec.get("high_confidence_zero_gain"):
                if dec.get("actual_success"):
                    streak = 0
                    prev_cls = None
                    confidences = []
                continue
            cls = dec.get("error_class")
            if prev_cls is None or cls == prev_cls:
                streak += 1
            else:
                streak = 1
            prev_cls = cls
            confidences.append(ac)
            if streak >= 2:
                trend = "flat"
                if len(confidences) >= 2:
                    if confidences[-1] > confidences[0] + 0.02:
                        trend = "increasing"
                    elif confidences[-1] < confidences[0] - 0.02:
                        trend = "decreasing"
                events.append(
                    {
                        "high_confidence_stuck": True,
                        "round": rnd,
                        "decision_id": dec.get("decision_id"),
                        "stuck_error_class": cls,
                        "confidence_trend": trend,
                        "no_gain_streak": streak,
                        "action_confidence": ac,
                    }
                )
    return events


def confidence_bucket(value):
    if value is None:
        return "missing"
    v = float(value)
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    for i in range(len(labels)):
        if edges[i] <= v < edges[i + 1]:
            return labels[i]
    return "0.8-1.0"


def summarize_calibration(linked_decisions):
    """confidence → outcome のバケット集計。"""
    buckets = defaultdict(
        lambda: {
            "n": 0,
            "success": 0,
            "useful_failure": 0,
            "zero_information_failure": 0,
            "information_gain": 0,
            "observation_missing": 0,
        }
    )
    source_stats = defaultdict(
        lambda: {"n": 0, "success": 0, "useful_failure": 0, "zero_information_failure": 0}
    )
    high_zero = 0
    high_repeat = 0
    high_n = 0
    total_with_obs = 0

    for dec in linked_decisions or []:
        ac = dec.get("action_confidence")
        bucket = confidence_bucket(ac)
        if ac is None:
            buckets[bucket]["observation_missing"] += 1
            buckets[bucket]["n"] += 1
            continue
        total_with_obs += 1
        buckets[bucket]["n"] += 1
        oc = dec.get("outcome_class")
        if oc == OUTCOME_SUCCESS:
            buckets[bucket]["success"] += 1
        elif oc == OUTCOME_USEFUL_FAILURE:
            buckets[bucket]["useful_failure"] += 1
        elif oc == OUTCOME_ZERO_INFO:
            buckets[bucket]["zero_information_failure"] += 1
        if dec.get("actual_information_gain"):
            buckets[bucket]["information_gain"] += 1

        pref = dec.get("preferred_source") or "unknown"
        source_stats[pref]["n"] += 1
        if oc == OUTCOME_SUCCESS:
            source_stats[pref]["success"] += 1
        elif oc == OUTCOME_USEFUL_FAILURE:
            source_stats[pref]["useful_failure"] += 1
        elif oc == OUTCOME_ZERO_INFO:
            source_stats[pref]["zero_information_failure"] += 1

        if ac >= HIGH_CONFIDENCE_THRESHOLD:
            high_n += 1
            if dec.get("actual_no_gain") or oc == OUTCOME_ZERO_INFO:
                high_zero += 1
            # repeating proxy: fail + same class already in no_gain
            if not dec.get("actual_success") and (
                dec.get("error_class") or dec.get("command_family")
            ):
                if dec.get("actual_no_gain"):
                    high_repeat += 1

    def _rates(row):
        n = row["n"] or 0
        if not n:
            return {**row, "success_rate": None, "useful_failure_rate": None,
                    "zero_information_failure_rate": None, "information_gain_rate": None}
        return {
            **row,
            "success_rate": round(row["success"] / n, 3),
            "useful_failure_rate": round(row["useful_failure"] / n, 3),
            "zero_information_failure_rate": round(
                row["zero_information_failure"] / n, 3
            ),
            "information_gain_rate": round(row["information_gain"] / n, 3),
        }

    return {
        "confidence_buckets": {
            k: _rates(v) for k, v in sorted(buckets.items(), key=lambda kv: kv[0])
        },
        "source_calibration": dict(source_stats),
        "high_confidence_zero_gain_rate": (
            round(high_zero / high_n, 3) if high_n else None
        ),
        "high_confidence_repeating_rate": (
            round(high_repeat / high_n, 3) if high_n else None
        ),
        "high_confidence_n": high_n,
        "decisions_with_observation": total_with_obs,
        "decisions_total": len(linked_decisions or []),
        "observation_coverage": (
            round(total_with_obs / len(linked_decisions), 3)
            if linked_decisions
            else None
        ),
        "not_for_decision": True,
        "phase": "kss-1",
    }


def observe_candidate_decision_payload(payload, candidates, *, round_num=None):
    """ask_json 直後: 観測抽出 + decision 付与 + 実行用候補は別途 strip。"""
    extracted = extract_payload_observation(payload)
    decisions = attach_decisions(candidates, extracted, round_num=round_num)
    return {
        "enabled": True,
        "phase": "kss-1",
        "not_for_decision": True,
        "prompt_injected_behavior_change": False,
        "round_observation": extracted.get("round_observation"),
        "decisions": decisions,
        "observation_coverage": (
            round(
                sum(1 for d in decisions if d.get("observation_present"))
                / max(len(decisions), 1),
                3,
            )
            if decisions
            else None
        ),
    }


def finalize_decision_observation(
    pre_obs,
    verified,
    state,
    *,
    round_num=None,
    coverage_before=None,
    event_ids=None,
):
    """verify + state 同期後に outcome を結ぶ。"""
    from tools.ai.state.knowledge_source import assess_known_coverage

    pre_obs = dict(pre_obs or {})
    if not pre_obs.get("enabled"):
        return {"enabled": False, "phase": "kss-1"}
    coverage_before = coverage_before or assess_known_coverage(state)
    coverage_after = assess_known_coverage(state)
    results = (verified or {}).get("results") if isinstance(verified, dict) else verified
    linked = link_decisions_to_results(
        pre_obs.get("decisions") or [],
        results,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
        history_event_ids=event_ids,
        stuck_error_class_before=coverage_before.get("stuck_error_class"),
    )
    pre_obs["round"] = round_num
    pre_obs["decisions"] = linked
    pre_obs["known_coverage_before"] = coverage_before
    pre_obs["known_coverage_after"] = coverage_after
    pre_obs["calibration_summary"] = summarize_calibration(linked)
    pre_obs["kss0_preferred_source"] = None
    return pre_obs


def record_decision_confidence_event(state, observation, *, round_num=None):
    if not observation or not observation.get("enabled"):
        return None
    history = getattr(state, "research_history", None)
    if history is None or not hasattr(history, "append"):
        return None
    summary = observation.get("calibration_summary") or {}
    return history.append(
        "decision_confidence_obs",
        action={"kind": "observe"},
        result={
            "observation_coverage": observation.get("observation_coverage"),
            "high_confidence_zero_gain_rate": summary.get(
                "high_confidence_zero_gain_rate"
            ),
            "decisions_with_observation": summary.get("decisions_with_observation"),
            "decisions_total": summary.get("decisions_total"),
        },
        metadata={"round": round_num, "not_for_decision": True, "phase": "kss-1"},
    )


def reanalyze_past_runs_note():
    """過去 run に confidence が無い場合の扱い。"""
    return {
        "confidence_in_past_runs": "missing",
        "note": "missing ≠ 0; do not invent confidence for past trials",
        "reusable_without_confidence": [
            "no_gain",
            "error_class_recurrence",
            "command_family_recurrence",
            "open_question_loop",
            "kss0_source_values",
        ],
    }
