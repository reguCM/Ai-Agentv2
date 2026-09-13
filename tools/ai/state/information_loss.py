"""
KSS-1.4: Research 経路分解・情報価値喪失点の観測（observation-only）。

チェーン:
  Web search → hit → kept → candidate → link → verify → usable → judge → progress → final

禁止: routing / confidence / HELP / Web強制 / 検索回数ルール /
      should_continue_web / 単一 confidence score /
      fail_stage 意味変更 / no_gain 意味変更

存在しない値は missing。新しい推定値は作らない。
"""

from __future__ import annotations

import os

MISSING = "missing"

LOSS_LABELS = (
    "SEARCH不足",
    "SEARCH→CANDIDATE変換不足",
    "LINK不足",
    "VERIFICATION不足",
    "JUDGE不足",
    "PROGRESS不足",
    "STAGNATION",
    "PROPOSAL_FAILURE",
)

WEB_VS_LLM_CASES = (
    "case1_no_web_hit",
    "case2_hit_no_candidate",
    "case3_candidate_no_link",
    "case4_candidate_verify_ng",
    "case5_usable_judge_ng",
    "case6_gain_then_no_gain_streak",
)


def kss14_obs_enabled() -> bool:
    raw = os.environ.get("AI_AGENT_KSS14_OBS")
    if raw is None or str(raw).strip() == "":
        raw = (
            os.environ.get("AI_AGENT_KSS13_OBS")
            or os.environ.get("AI_AGENT_KSS12_OBS")
            or os.environ.get("AI_AGENT_KSS11_OBS")
        )
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _missing():
    return MISSING


def _is_missing(v):
    return v is None or v == MISSING


def _num(v):
    if _is_missing(v):
        return None
    if isinstance(v, bool):
        return int(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _truthy_count(n):
    """count>0 → True, count==0 → False, missing → missing."""
    if n is None or _is_missing(n):
        return _missing()
    try:
        return int(n) > 0
    except (TypeError, ValueError):
        return _missing()


def _stage(name, *, count=None, available=None, provenance=None, rejection=None, failure_reason=None):
    return {
        "stage": name,
        "count": count if count is not None else _missing(),
        "available": available if available is not None else _missing(),
        "provenance": provenance if provenance is not None else _missing(),
        "rejection": rejection if rejection is not None else _missing(),
        "failure_reason": failure_reason if failure_reason is not None else _missing(),
    }


def _from_kss13(kss13):
    kss13 = kss13 or {}
    sv = kss13.get("search_volume") or {}
    lead = kss13.get("exploration_leads") or {}
    nov = kss13.get("information_novelty") or {}
    es = kss13.get("evidence_strength") or {}
    return {
        "search_result_count": sv.get("search_result_count", _missing()),
        "kept_hit_count": sv.get("kept_hit_count"),
        "dropped_hit_count": sv.get("dropped_hit_count", _missing()),
        "candidate_count": lead.get("candidate_count"),
        "linked_candidate_count": lead.get("linked_candidate_count"),
        "zero_overlap_count": lead.get("zero_overlap_count"),
        "link_coverage": lead.get("link_coverage"),
        "new_source_count": nov.get("new_source_count"),
        "new_term_count": nov.get("new_term_count"),
        "new_url_count": nov.get("new_url_count"),
        "no_gain_existing": kss13.get("no_gain_existing", _missing()),
        "information_gain_existing": kss13.get("information_gain_existing", _missing()),
        "progress_action": kss13.get("progress_action", _missing()),
        "progress_reason": kss13.get("progress_reason", _missing()),
        "evidence_level": es.get("evidence_level", _missing()),
        "verify_high_count": es.get("verify_high_count", _missing()),
        "verify_low_count": es.get("verify_low_count", _missing()),
        "usable_count": es.get("usable_count", _missing()),
        "run_linkage": kss13.get("run_linkage") or {},
    }


def _from_round_item(round_item):
    round_item = round_item or {}
    de = round_item.get("decision_evidence_observation") or {}
    evd = de.get("evidence") or {} if isinstance(de, dict) else {}
    verified_runs = round_item.get("verified_runs") or []
    verify_ok = sum(1 for r in verified_runs if isinstance(r, dict) and r.get("ok"))
    verify_fail = sum(
        1 for r in verified_runs if isinstance(r, dict) and r.get("ok") is False
    )
    judge_sat = round_item.get("satisfies_request")
    if judge_sat is None and de.get("enabled"):
        for ev in de.get("decision_events") or []:
            if ev.get("decision_type") == "research_judge":
                judge_sat = ev.get("judge_satisfies_request")
                if judge_sat is None:
                    judge_sat = ev.get("final_decision")
                break
    usable = evd.get("usable_count")
    if usable is None or _is_missing(usable):
        # verified high as proxy only if usable missing — still count from evidence
        usable = _missing()
    return {
        "candidate_count_fallback": round_item.get("candidate_count"),
        "verified_count": round_item.get("verified_count"),
        "verify_ok_runs": verify_ok,
        "verify_fail_runs": verify_fail,
        "verifier_failure": round_item.get("verifier_failure"),
        "judge_satisfied": judge_sat if judge_sat is not None else _missing(),
        "usable_count": usable if usable is not None else evd.get("usable_count", _missing()),
        "verify_high_count": evd.get("verify_high_count", _missing()),
        "verify_low_count": evd.get("verify_low_count", _missing()),
        "candidates_rejected_count": evd.get("candidates_rejected_count", _missing()),
        "web_kept_count": evd.get("web_kept_count", _missing()),
        "evidence_level": evd.get("evidence_level", _missing()),
        "no_gain": evd.get("no_gain", _missing()),
        "web_hits_len": len(round_item.get("web_hits") or []),
    }


def observe_information_loss_round(
    *,
    round_num,
    kss13_bundle=None,
    round_item=None,
    case_id=None,
    research_run_id=None,
):
    """1 round の経路チェーン + 喪失点フラグ。判断には使わない。"""
    x = _from_kss13(kss13_bundle)
    r = _from_round_item(round_item)

    kept = x.get("kept_hit_count")
    if kept is None or _is_missing(kept):
        kept = r.get("web_kept_count")
        if _is_missing(kept):
            kept = r.get("web_hits_len")

    search_raw = x.get("search_result_count")
    dropped = x.get("dropped_hit_count")

    cand = x.get("candidate_count")
    if cand is None or _is_missing(cand):
        cand = r.get("candidate_count_fallback")

    linked = x.get("linked_candidate_count")
    zero_ov = x.get("zero_overlap_count")
    link_cov = x.get("link_coverage")

    verify_high = x.get("verify_high_count")
    if _is_missing(verify_high):
        verify_high = r.get("verify_high_count")
    verify_low = x.get("verify_low_count")
    if _is_missing(verify_low):
        verify_low = r.get("verify_low_count")
    verify_ok = r.get("verify_ok_runs")
    verify_fail = r.get("verify_fail_runs")

    usable = x.get("usable_count")
    if _is_missing(usable):
        usable = r.get("usable_count")

    judge_sat = r.get("judge_satisfied")
    progress_action = x.get("progress_action")
    progress_reason = x.get("progress_reason")

    no_gain = x.get("no_gain_existing")
    if _is_missing(no_gain):
        no_gain = r.get("no_gain")
    info_gain = x.get("information_gain_existing")
    has_gain = _missing()
    if isinstance(info_gain, dict) and "has_gain" in info_gain:
        has_gain = bool(info_gain.get("has_gain"))
    elif no_gain is True:
        has_gain = False
    elif no_gain is False:
        has_gain = _missing()  # no_gain False ≠ has_gain True を捏造しない

    # boolean stage flags（既存 count から）
    flags = {
        "web_hit_available": _truthy_count(
            search_raw if not _is_missing(search_raw) else kept
        ),
        "web_hit_kept": _truthy_count(kept),
        "candidate_available": _truthy_count(cand),
        "candidate_linked": _truthy_count(linked),
        "candidate_verified": _truthy_count(
            verify_high if not _is_missing(verify_high) else verify_ok
        ),
        "usable_finding_available": _truthy_count(usable),
        "judge_satisfied": (
            bool(judge_sat) if not _is_missing(judge_sat) else _missing()
        ),
        "progress_action": progress_action,
    }

    chain = [
        _stage(
            "web_search",
            count=search_raw,
            available=_truthy_count(search_raw)
            if not _is_missing(search_raw)
            else _missing(),
            provenance="web_exec_stats.search_result_count",
            rejection=dropped,
        ),
        _stage(
            "web_hit",
            count=kept if not _is_missing(search_raw) else kept,
            available=_truthy_count(kept),
            provenance="web_hits / kept_hit_count",
        ),
        _stage(
            "kept_hit",
            count=kept,
            available=_truthy_count(kept),
            provenance="filter_relevant_hits kept",
            rejection=dropped,
        ),
        _stage(
            "candidate",
            count=cand,
            available=_truthy_count(cand),
            provenance="LLM candidates after reject filter",
            rejection=r.get("candidates_rejected_count"),
        ),
        _stage(
            "candidate_hit_link",
            count=linked,
            available=_truthy_count(linked),
            provenance="KSS-1.2 token_overlap",
            rejection=zero_ov,
            failure_reason=(
                "zero_overlap"
                if (_num(zero_ov) or 0) > 0 and (_num(linked) or 0) == 0
                else _missing()
            ),
        ),
        _stage(
            "verification",
            count=verify_ok if verify_ok is not None else verify_high,
            available=_truthy_count(
                verify_high if not _is_missing(verify_high) else verify_ok
            ),
            provenance="research_verifier / verify_high",
            rejection=verify_fail if verify_fail else verify_low,
            failure_reason=(
                "verifier_failure"
                if r.get("verifier_failure")
                else _missing()
            ),
        ),
        _stage(
            "usable_finding",
            count=usable,
            available=_truthy_count(usable),
            provenance="pack usable_findings / evidence.usable_count",
        ),
        _stage(
            "judge",
            count=1 if judge_sat is True else (0 if judge_sat is False else _missing()),
            available=flags["judge_satisfied"],
            provenance="judgment.satisfies_request",
            failure_reason=(
                "not_satisfied" if judge_sat is False else _missing()
            ),
        ),
        _stage(
            "progress",
            count=_missing(),
            available=progress_action not in (None, MISSING),
            provenance="evaluate_research_progress",
            failure_reason=progress_reason,
        ),
    ]

    first_loss = detect_first_loss_point(flags, counts={
        "kept": kept,
        "candidate": cand,
        "linked": linked,
        "verified": verify_high if not _is_missing(verify_high) else verify_ok,
        "usable": usable,
        "judge": judge_sat,
        "progress": progress_action,
    })

    web_vs_llm = classify_web_vs_llm_round(flags, no_gain=no_gain, has_gain=has_gain)

    run_link = dict(x.get("run_linkage") or {})
    if case_id is not None:
        run_link["case_id"] = case_id
    if research_run_id is not None:
        run_link["research_run_id"] = research_run_id
    run_link["round_index"] = round_num

    return {
        "enabled": True,
        "phase": "kss-1.4",
        "not_for_decision": True,
        "behavior_changed": False,
        "round_index": round_num,
        "chain": chain,
        "stage_flags": flags,
        "counts": {
            "search_result_count": search_raw,
            "kept_hit_count": kept,
            "dropped_hit_count": dropped,
            "candidate_count": cand,
            "linked_candidate_count": linked,
            "zero_overlap_count": zero_ov,
            "link_coverage": link_cov,
            "verify_ok_count": verify_ok,
            "verify_fail_count": verify_fail,
            "verify_high_count": verify_high,
            "verify_low_count": verify_low,
            "usable_count": usable,
            "new_source_count": x.get("new_source_count"),
            "new_term_count": x.get("new_term_count"),
            "new_url_count": x.get("new_url_count"),
        },
        "current_round_gain": has_gain,
        "no_gain_existing": no_gain,
        "information_gain_existing": info_gain,
        "first_loss_point": first_loss,
        "web_vs_llm_hypothesis": web_vs_llm,
        "progress_action": progress_action,
        "progress_reason": progress_reason,
        "run_linkage": run_link,
        "should_continue_web": _missing(),  # 明示的に未実装
        "confidence_score": _missing(),
        "missing_fields_policy": "missing_not_zero",
    }


def detect_first_loss_point(flags, counts):
    """
    上流→下流で最初に available=False / count=0 になる点。
    judge/progress は boolean / action。責任判定ではない。
    """
    order = [
        ("web_hit_kept", "kept", "SEARCH不足"),
        ("candidate_available", "candidate", "SEARCH→CANDIDATE変換不足"),
        ("candidate_linked", "linked", "LINK不足"),
        ("candidate_verified", "verified", "VERIFICATION不足"),
        ("usable_finding_available", "usable", "VERIFICATION不足"),
        ("judge_satisfied", "judge", "JUDGE不足"),
    ]
    for flag_key, count_key, label in order:
        avail = flags.get(flag_key)
        if avail is False:
            return {
                "stage": flag_key,
                "observational_label": label,
                "count": counts.get(count_key, _missing()),
                "note": "first False/zero along chain; not blame assignment",
            }
        n = _num(counts.get(count_key))
        if n is not None and n == 0 and flag_key != "judge_satisfied":
            return {
                "stage": flag_key,
                "observational_label": label,
                "count": 0,
                "note": "first zero count along chain; not blame assignment",
            }
    # progress not advancing while earlier stages ok
    if flags.get("progress_action") == "continue" and flags.get("judge_satisfied") is not True:
        return {
            "stage": "progress_action",
            "observational_label": "PROGRESS不足",
            "count": _missing(),
            "note": "continue without satisfy; observational only",
        }
    if flags.get("progress_action") in ("stop",):
        return {
            "stage": "progress_stop",
            "observational_label": "STAGNATION",
            "count": _missing(),
            "note": "stop action; check progress_reason separately",
        }
    return {
        "stage": "none_detected",
        "observational_label": _missing(),
        "count": _missing(),
        "note": "no clear zero/False along chain for this round",
    }


def classify_web_vs_llm_round(flags, *, no_gain=None, has_gain=None):
    """仮説分類（自動責任判定ではない）。"""
    labels = []
    hit = flags.get("web_hit_kept")
    cand = flags.get("candidate_available")
    linked = flags.get("candidate_linked")
    verified = flags.get("candidate_verified")
    usable = flags.get("usable_finding_available")
    judge = flags.get("judge_satisfied")

    if hit is False:
        labels.append("case1_no_web_hit")
    if hit is True and cand is False:
        labels.append("case2_hit_no_candidate")
    if cand is True and linked is False:
        labels.append("case3_candidate_no_link")
    if cand is True and verified is False:
        labels.append("case4_candidate_verify_ng")
    if usable is True and judge is False:
        labels.append("case5_usable_judge_ng")
    if has_gain is True or (no_gain is False and has_gain is not False):
        # streak は run レベルで見る
        pass
    if no_gain is True:
        labels.append("round_no_gain")

    return {
        "labels": labels or ["none"],
        "not_blame_assignment": True,
        "note": "hypothesis classification for analysis only",
    }


def classify_run_loss_labels(trajectory_rounds, *, fail_stage=None, stop_reason=None, final_pass=None):
    """run 全体の観測ラベル（fail_stage は変更しない）。"""
    labels = []
    notes = []
    rounds = trajectory_rounds or []

    if not rounds:
        if fail_stage and "proposal" in str(fail_stage).lower():
            labels.append("PROPOSAL_FAILURE")
        else:
            labels.append("PROPOSAL_FAILURE")
        notes.append("zero research rounds")
        return {"labels": labels, "notes": notes, "fail_stage_unchanged": fail_stage}

    any_kept = any(
        (r.get("stage_flags") or {}).get("web_hit_kept") is True for r in rounds
    )
    any_cand = any(
        (r.get("stage_flags") or {}).get("candidate_available") is True for r in rounds
    )
    weak_link = sum(
        1
        for r in rounds
        if (r.get("stage_flags") or {}).get("candidate_available") is True
        and (r.get("stage_flags") or {}).get("candidate_linked") is False
    )
    any_usable = any(
        (r.get("stage_flags") or {}).get("usable_finding_available") is True
        for r in rounds
    )
    judge_true = any(
        (r.get("stage_flags") or {}).get("judge_satisfied") is True for r in rounds
    )
    judge_false_with_usable = any(
        (r.get("stage_flags") or {}).get("usable_finding_available") is True
        and (r.get("stage_flags") or {}).get("judge_satisfied") is False
        for r in rounds
    )

    kept_max = max(
        (_num((r.get("counts") or {}).get("kept_hit_count")) or 0) for r in rounds
    )
    if not any_kept or kept_max <= 0:
        labels.append("SEARCH不足")
        notes.append("no kept web hits across rounds")

    if any_kept and not any_cand:
        labels.append("SEARCH→CANDIDATE変換不足")
        notes.append("hits present but no candidates")

    if weak_link >= max(1, len(rounds) // 3):
        labels.append("LINK不足")
        notes.append("many rounds with candidate but no hit link")

    if any_cand and not any_usable:
        labels.append("VERIFICATION不足")
        notes.append("candidates exist but no usable finding")

    if judge_false_with_usable or (any_usable and not judge_true and final_pass is False):
        labels.append("JUDGE不足")
        notes.append("usable present but judge not satisfied / no implement")

    # progress: novelty or gain but never implement
    novelty = any(
        (_num((r.get("counts") or {}).get("new_term_count")) or 0) > 0
        or (_num((r.get("counts") or {}).get("new_source_count")) or 0) > 0
        for r in rounds
    )
    implement = any(r.get("progress_action") == "implement" for r in rounds)
    if novelty and not implement and final_pass is False:
        labels.append("PROGRESS不足")
        notes.append("novelty observed but never implement")

    no_gain_streak = 0
    max_streak = 0
    for r in rounds:
        if r.get("no_gain_existing") is True:
            no_gain_streak += 1
            max_streak = max(max_streak, no_gain_streak)
        else:
            no_gain_streak = 0
    if max_streak >= 2 or stop_reason in ("stagnation", "max_research_rounds"):
        if max_streak >= 2 or stop_reason == "stagnation":
            labels.append("STAGNATION")
            notes.append(f"no_gain_streak_max={max_streak} stop={stop_reason}")

    if fail_stage and str(fail_stage).startswith("proposal"):
        labels.append("PROPOSAL_FAILURE")

    if final_pass:
        labels.append("success_trajectory")
    elif not labels:
        labels.append("unclassified_failure")

    # earliest first_loss across rounds
    firsts = []
    for r in rounds:
        fl = r.get("first_loss_point") or {}
        if fl.get("observational_label") not in (None, MISSING, "none_detected"):
            firsts.append(
                {
                    "round": r.get("round_index"),
                    "label": fl.get("observational_label"),
                    "stage": fl.get("stage"),
                }
            )

    return {
        "labels": labels,
        "notes": notes,
        "fail_stage_unchanged": fail_stage,
        "earliest_loss_events": firsts[:5],
        "first_loss_in_run": firsts[0] if firsts else None,
    }


def attach_next_round_gain(bundles):
    out = []
    n = len(bundles or [])
    for i, b in enumerate(bundles or []):
        item = dict(b)
        link = dict(item.get("run_linkage") or {})
        link["next_round_exists"] = i + 1 < n
        if i + 1 < n:
            nxt = bundles[i + 1]
            link["next_round_gain"] = nxt.get("current_round_gain")
            if _is_missing(link["next_round_gain"]):
                ng = nxt.get("no_gain_existing")
                if ng is True:
                    link["next_round_gain"] = False
                elif ng is False:
                    # 捏造しない: no_gain False だけでは gain としない
                    nov = (nxt.get("counts") or {})
                    link["next_round_gain"] = bool(
                        (_num(nov.get("new_term_count")) or 0) > 0
                        or (_num(nov.get("new_source_count")) or 0) > 0
                        or (_num(nov.get("new_url_count")) or 0) > 0
                    )
        else:
            link["next_round_gain"] = _missing()
        item["run_linkage"] = link
        item["next_round_gain"] = link["next_round_gain"]
        out.append(item)
    return out


def build_trajectory(
    *,
    case_id,
    rounds_kss13=None,
    round_details=None,
    final_pass=None,
    fail_stage=None,
    fail_reason=None,
    stop_reason=None,
    research_run_id=None,
):
    """run の時系列 trajectory を再構築。"""
    details_by_round = {}
    for item in round_details or []:
        if isinstance(item, dict) and item.get("round") is not None:
            details_by_round[item["round"]] = item

    bundles = []
    if rounds_kss13:
        for k13 in rounds_kss13:
            if not isinstance(k13, dict):
                continue
            rnd = k13.get("round_index")
            bundles.append(
                observe_information_loss_round(
                    round_num=rnd,
                    kss13_bundle=k13,
                    round_item=details_by_round.get(rnd),
                    case_id=case_id,
                    research_run_id=research_run_id,
                )
            )
    else:
        for rnd, item in sorted(details_by_round.items()):
            k13 = item.get("exploration_value_observation")
            bundles.append(
                observe_information_loss_round(
                    round_num=rnd,
                    kss13_bundle=k13 if isinstance(k13, dict) else {},
                    round_item=item,
                    case_id=case_id,
                    research_run_id=research_run_id,
                )
            )

    bundles = attach_next_round_gain(bundles)
    for b in bundles:
        link = b.setdefault("run_linkage", {})
        link["final_pass"] = final_pass
        link["fail_stage"] = fail_stage if fail_stage is not None else _missing()
        link["fail_reason"] = fail_reason if fail_reason is not None else _missing()
        link["total_rounds"] = len(bundles)
        link["eventually_succeeded"] = (
            bool(final_pass) if final_pass is not None else _missing()
        )
        b["eventual_success"] = link["eventually_succeeded"]

    run_class = classify_run_loss_labels(
        bundles,
        fail_stage=fail_stage,
        stop_reason=stop_reason,
        final_pass=final_pass,
    )

    # case6: gain-like then no_gain streak
    web_llm_run = []
    saw_lead = False
    for b in bundles:
        counts = b.get("counts") or {}
        lead = (
            (_num(counts.get("new_term_count")) or 0) > 0
            or (_num(counts.get("new_source_count")) or 0) > 0
        )
        if lead:
            saw_lead = True
        if saw_lead and b.get("no_gain_existing") is True:
            web_llm_run.append("case6_gain_then_no_gain_streak")
            break
    for b in bundles:
        for lab in (b.get("web_vs_llm_hypothesis") or {}).get("labels") or []:
            if lab not in web_llm_run and lab != "none":
                web_llm_run.append(lab)

    trajectory = {
        "enabled": True,
        "phase": "kss-1.4",
        "not_for_decision": True,
        "case_id": case_id,
        "research_run_id": research_run_id,
        "rounds": [
            {
                "round_index": b.get("round_index"),
                "hit": (b.get("counts") or {}).get("kept_hit_count"),
                "candidate": (b.get("counts") or {}).get("candidate_count"),
                "linked": (b.get("counts") or {}).get("linked_candidate_count"),
                "usable": (b.get("counts") or {}).get("usable_count"),
                "verify_ok": (b.get("counts") or {}).get("verify_ok_count"),
                "gain": b.get("current_round_gain"),
                "no_gain": b.get("no_gain_existing"),
                "new_source": (b.get("counts") or {}).get("new_source_count"),
                "new_term": (b.get("counts") or {}).get("new_term_count"),
                "link_coverage": (b.get("counts") or {}).get("link_coverage"),
                "judge_satisfied": (b.get("stage_flags") or {}).get("judge_satisfied"),
                "progress_action": b.get("progress_action"),
                "progress_reason": b.get("progress_reason"),
                "first_loss_point": b.get("first_loss_point"),
                "next_round_gain": b.get("next_round_gain"),
                "stage_flags": b.get("stage_flags"),
            }
            for b in bundles
        ],
        "round_observations": bundles,
        "final": {
            "success": final_pass,
            "fail_stage": fail_stage,
            "fail_reason": fail_reason,
            "stop_reason": stop_reason,
            "total_rounds": len(bundles),
        },
        "run_loss_classification": run_class,
        "web_vs_llm_run_labels": web_llm_run,
        "contrast_note": (
            "memory_usage may succeed with link_coverage=0; "
            "do not assume linkage implies success"
        ),
        "routing_options_not_executed": ["A", "B", "C", "D", "E", "F"],
    }
    return trajectory


def maybe_observe_information_loss_round(**kwargs):
    if not kss14_obs_enabled():
        return {"enabled": False, "phase": "kss-1.4"}
    return observe_information_loss_round(**kwargs)
