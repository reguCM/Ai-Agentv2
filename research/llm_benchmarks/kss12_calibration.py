"""
KSS-1.2: Verifier / Rule 校正 + Web↔decision 紐付け監査。

オフライン再分析が主。routing / confidence 閾値は実装しない。
missing ≠ 0。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _missing():
    return "missing"


def _rate_rows(counter, left_name):
    """counter keys: (left, right) -> n"""
    grouped = defaultdict(Counter)
    totals = Counter()
    for (left, right), n in counter.items():
        grouped[left][right] += n
        totals[left] += n
    rows = []
    for left, outcomes in grouped.items():
        t = totals[left] or 1
        rows.append(
            {
                left_name: left,
                "n": totals[left],
                "outcome_rates": {str(k): round(v / t, 3) for k, v in outcomes.items()},
                "outcome_counts": dict(outcomes),
            }
        )
    rows.sort(key=lambda r: (-r["n"], str(r[left_name])))
    return rows


def _progress_action_from_round(item, progress_by_round=None):
    de = item.get("decision_evidence_observation") or {}
    for ev in de.get("decision_events") or []:
        if ev.get("decision_type") == "research_progress":
            act = ev.get("progress_action") or ev.get("final_decision")
            if act not in (None, "", _missing()):
                return act
    rnd = item.get("round")
    if progress_by_round and rnd in progress_by_round:
        return progress_by_round[rnd]
    return _missing()


def _retro_web_link(item):
    """
    保存済み web_hits に score が無くても、既存 hit_score + token overlap で
    事後監査する（行動変更なし・推定で decision は作らない）。
    """
    from tools.ai.state.web_decision_link import link_candidates_to_hits

    hits = item.get("web_hits") or []
    # verified_runs / candidate_keys を擬似候補にする
    cands = []
    for run in item.get("verified_runs") or []:
        if not isinstance(run, dict):
            continue
        cands.append(
            {
                "command": run.get("command"),
                "args": list(run.get("args") or []),
                "question": "",
                "route": "verified_run",
            }
        )
    if not cands:
        for key in item.get("candidate_keys") or []:
            cands.append({"command": str(key), "args": [], "route": "candidate_key"})
    if not hits and not cands:
        return {
            "enabled": True,
            "retroactive": True,
            "candidates_total": 0,
            "candidates_linked": 0,
            "hits_total": 0,
            "audit_gaps": ["no_web_hits_in_round", "no_candidates_for_link"],
            "link_coverage": None,
        }
    linked = link_candidates_to_hits(cands, hits)
    linked["retroactive"] = True
    return linked


def calibrate_from_rounds(rounds, *, run_meta=None, progress_log=None):
    run_meta = run_meta or {}
    progress_by_round = {}
    for p in progress_log or []:
        if isinstance(p, dict) and p.get("round") is not None:
            progress_by_round[p["round"]] = p.get("action")

    verify_label_vs_progress = Counter()
    verify_ok_round_vs_progress = Counter()
    evidence_level_vs_progress = Counter()
    evidence_level_vs_case_pass = Counter()
    progress_counts = Counter()
    judge_sat_vs_progress = Counter()
    no_gain_vs_progress = Counter()
    rule_reason_vs_progress = Counter()

    web_stats = {
        "rounds_total": 0,
        "rounds_with_hits": 0,
        "candidates_total": 0,
        "candidates_linked": 0,
        "hit_score_present_saved": 0,
        "hit_score_missing_saved": 0,
        "hit_score_computed_retro": 0,
        "audit_gaps": Counter(),
        "overlap_hist": Counter(),
    }

    case_pass = run_meta.get("pass")
    case_pass_label = (
        "pass" if case_pass is True else ("fail" if case_pass is False else _missing())
    )

    for item in rounds or []:
        if not isinstance(item, dict):
            continue
        web_stats["rounds_total"] += 1
        progress_action = _progress_action_from_round(item, progress_by_round)
        progress_counts[progress_action] += 1

        de = item.get("decision_evidence_observation") or {}
        evd = de.get("evidence") or {} if de.get("enabled") else {}

        if de.get("enabled"):
            level = evd.get("evidence_level") or _missing()
            evidence_level_vs_progress[(level, progress_action)] += 1
            evidence_level_vs_case_pass[(level, case_pass_label)] += 1
            no_gain = evd.get("no_gain")
            if no_gain is not None and no_gain != _missing():
                no_gain_vs_progress[(bool(no_gain), progress_action)] += 1
            for label in evd.get("verify_confidence_labels") or []:
                verify_label_vs_progress[(label or _missing(), progress_action)] += 1
            # saved web scores
            for sc in evd.get("web_hit_scores") or []:
                if sc == _missing() or sc is None:
                    web_stats["hit_score_missing_saved"] += 1
                else:
                    web_stats["hit_score_present_saved"] += 1
            for ev in de.get("decision_events") or []:
                if ev.get("decision_type") == "research_judge":
                    sat = ev.get("judge_satisfies_request")
                    if sat is None:
                        sat = ev.get("final_decision")
                    judge_sat_vs_progress[(bool(sat), progress_action)] += 1
                if ev.get("decision_type") == "research_progress":
                    reason = ev.get("progress_reason") or _missing()
                    rule_reason_vs_progress[(reason, progress_action)] += 1

        # verified_runs fallback for label
        if not (evd.get("verify_confidence_labels") or []):
            for run in item.get("verified_runs") or []:
                if not isinstance(run, dict):
                    continue
                label = run.get("confidence") or (
                    "high" if run.get("ok") else "low"
                )
                verify_label_vs_progress[(label, progress_action)] += 1

        had_ok = any(
            isinstance(r, dict) and r.get("ok") for r in (item.get("verified_runs") or [])
        )
        verify_ok_round_vs_progress[(had_ok, progress_action)] += 1

        # Web link audit (prefer live obs, else retro)
        wlink = item.get("web_decision_link")
        if not (isinstance(wlink, dict) and wlink.get("enabled")):
            wlink = _retro_web_link(item)
        if item.get("web_hits"):
            web_stats["rounds_with_hits"] += 1
        if isinstance(wlink, dict) and wlink.get("enabled"):
            web_stats["candidates_total"] += int(wlink.get("candidates_total") or 0)
            web_stats["candidates_linked"] += int(wlink.get("candidates_linked") or 0)
            for h in wlink.get("hits_scored") or []:
                if h.get("score") is None or h.get("score") == _missing():
                    pass
                else:
                    web_stats["hit_score_computed_retro"] += 1
            for link in wlink.get("candidate_hit_links") or []:
                ov = int(link.get("token_overlap") or 0)
                web_stats["overlap_hist"][ov if ov <= 5 else "6+"] += 1
            for g in wlink.get("audit_gaps") or []:
                web_stats["audit_gaps"][g] += 1

    return {
        "run": {
            "case": run_meta.get("case"),
            "pass": run_meta.get("pass"),
            "fail_stage": run_meta.get("fail_stage"),
            "request": run_meta.get("request"),
        },
        "progress_action_counts": dict(progress_counts),
        "verifier_label_vs_progress": _rate_rows(
            verify_label_vs_progress, "verify_confidence_label"
        ),
        "round_had_verify_ok_vs_progress": _rate_rows(
            verify_ok_round_vs_progress, "had_verify_ok"
        ),
        "evidence_level_vs_progress": _rate_rows(
            evidence_level_vs_progress, "evidence_level"
        ),
        "evidence_level_vs_case_pass": _rate_rows(
            evidence_level_vs_case_pass, "evidence_level"
        ),
        "judge_satisfies_vs_progress": _rate_rows(
            judge_sat_vs_progress, "judge_satisfies"
        ),
        "no_gain_vs_progress": _rate_rows(no_gain_vs_progress, "no_gain"),
        "rule_reason_vs_progress": _rate_rows(
            rule_reason_vs_progress, "progress_reason"
        ),
        "web_decision_link_audit": {
            "rounds_total": web_stats["rounds_total"],
            "rounds_with_hits": web_stats["rounds_with_hits"],
            "candidates_total": web_stats["candidates_total"],
            "candidates_linked": web_stats["candidates_linked"],
            "link_coverage": (
                round(
                    web_stats["candidates_linked"] / web_stats["candidates_total"],
                    3,
                )
                if web_stats["candidates_total"]
                else None
            ),
            "hit_score_present_saved": web_stats["hit_score_present_saved"],
            "hit_score_missing_saved": web_stats["hit_score_missing_saved"],
            "hit_score_computed_retro": web_stats["hit_score_computed_retro"],
            "overlap_hist": {str(k): v for k, v in web_stats["overlap_hist"].items()},
            "audit_gaps": dict(web_stats["audit_gaps"]),
        },
    }


def calibrate_experiment_dir(exp_dir: Path):
    exp_dir = Path(exp_dir)
    per_case = []
    merged = {
        "verifier_label_vs_progress": Counter(),
        "evidence_level_vs_progress": Counter(),
        "evidence_level_vs_case_pass": Counter(),
        "round_had_verify_ok_vs_progress": Counter(),
        "judge_satisfies_vs_progress": Counter(),
        "no_gain_vs_progress": Counter(),
        "rule_reason_vs_progress": Counter(),
    }
    web_totals = Counter()
    gap_totals = Counter()
    overlap_totals = Counter()

    for path in sorted(exp_dir.glob("*.json")):
        if path.name in (
            "summary.json",
            "manifest.json",
            "calibration.json",
            "kss12_calibration.json",
        ):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        pipe = rec.get("pipeline") or {}
        rounds = pipe.get("research_rounds_detail") or []
        progress = pipe.get("progress") or []
        metrics = rec.get("metrics") or {}
        cal = calibrate_from_rounds(
            rounds,
            run_meta={
                "pass": metrics.get("pass", rec.get("pass")),
                "fail_stage": metrics.get("fail_stage", rec.get("fail_stage")),
                "request": rec.get("request"),
                "case": rec.get("case"),
            },
            progress_log=progress,
        )
        per_case.append({"case": rec.get("case"), "file": path.name, "calibration": cal})

        def _absorb(section, dest_key, left_field):
            for row in cal.get(section) or []:
                left = row.get(left_field)
                for outcome, n in (row.get("outcome_counts") or {}).items():
                    merged[dest_key][(left, outcome)] += n

        _absorb(
            "verifier_label_vs_progress",
            "verifier_label_vs_progress",
            "verify_confidence_label",
        )
        _absorb(
            "evidence_level_vs_progress",
            "evidence_level_vs_progress",
            "evidence_level",
        )
        _absorb(
            "evidence_level_vs_case_pass",
            "evidence_level_vs_case_pass",
            "evidence_level",
        )
        _absorb(
            "round_had_verify_ok_vs_progress",
            "round_had_verify_ok_vs_progress",
            "had_verify_ok",
        )
        _absorb(
            "judge_satisfies_vs_progress",
            "judge_satisfies_vs_progress",
            "judge_satisfies",
        )
        _absorb("no_gain_vs_progress", "no_gain_vs_progress", "no_gain")
        _absorb("rule_reason_vs_progress", "rule_reason_vs_progress", "progress_reason")

        w = cal.get("web_decision_link_audit") or {}
        for k in (
            "rounds_total",
            "rounds_with_hits",
            "candidates_total",
            "candidates_linked",
            "hit_score_present_saved",
            "hit_score_missing_saved",
            "hit_score_computed_retro",
        ):
            web_totals[k] += int(w.get(k) or 0)
        for g, n in (w.get("audit_gaps") or {}).items():
            gap_totals[g] += n
        for ov, n in (w.get("overlap_hist") or {}).items():
            overlap_totals[ov] += n

    return {
        "phase": "kss-1.2",
        "experiment_dir": str(exp_dir),
        "not_for_decision": True,
        "routing_implemented": False,
        "confidence_threshold_implemented": False,
        "per_case": per_case,
        "aggregate": {
            "verifier_label_vs_progress": _rate_rows(
                merged["verifier_label_vs_progress"], "verify_confidence_label"
            ),
            "evidence_level_vs_progress": _rate_rows(
                merged["evidence_level_vs_progress"], "evidence_level"
            ),
            "evidence_level_vs_case_pass": _rate_rows(
                merged["evidence_level_vs_case_pass"], "evidence_level"
            ),
            "round_had_verify_ok_vs_progress": _rate_rows(
                merged["round_had_verify_ok_vs_progress"], "had_verify_ok"
            ),
            "judge_satisfies_vs_progress": _rate_rows(
                merged["judge_satisfies_vs_progress"], "judge_satisfies"
            ),
            "no_gain_vs_progress": _rate_rows(
                merged["no_gain_vs_progress"], "no_gain"
            ),
            "rule_reason_vs_progress": _rate_rows(
                merged["rule_reason_vs_progress"], "progress_reason"
            ),
            "web_decision_link_audit": {
                **dict(web_totals),
                "link_coverage": (
                    round(
                        web_totals["candidates_linked"] / web_totals["candidates_total"],
                        3,
                    )
                    if web_totals["candidates_total"]
                    else None
                ),
                "audit_gaps": dict(gap_totals),
                "overlap_hist": dict(overlap_totals),
                "note": (
                    "Saved KSS-1.1 runs omit hit.score on web_hits; "
                    "retroactive audit recomputes existing hit_score and "
                    "token-overlap links to verified_runs (observational only)."
                ),
            },
        },
        "code_linkage_audit": audit_code_linkage(),
        "interpretation_hints": {
            "verifier_high_should_correlate_with_implement": True,
            "web_link_gap": (
                "Candidates are LLM-proposed; no hard FK to hit.url existed. "
                "KSS-1.2 adds observational token-overlap links only."
            ),
            "do_not_set_thresholds_yet": True,
        },
    }


def audit_code_linkage():
    return {
        "web_search_produces_hits": True,
        "hit_score_exists": True,
        "hit_score_path": "tools/system/tool_builder/research/web.py:hit_score",
        "hits_reach_candidate_prompt": True,
        "candidate_json_has_hit_url_field": False,
        "verifier_reads_hit_score": False,
        "progress_reads_hit_score": False,
        "round_details_web_hits_include_score_before_kss12": False,
        "linkage_before_kss12": "missing",
        "linkage_after_kss12_obs": "token_overlap_observational_only",
        "routing_on_web_score": False,
        "env_flag": "AI_AGENT_KSS12_OBS (also inherits AI_AGENT_KSS11_OBS)",
    }


def write_report_md(report: dict, out_path: Path):
    agg = report.get("aggregate") or {}
    web = agg.get("web_decision_link_audit") or {}
    lines = [
        "# KSS-1.2 Calibration & Web↔Decision Link Audit",
        "",
        f"- experiment_dir: `{report.get('experiment_dir')}`",
        f"- routing_implemented: `{report.get('routing_implemented')}`",
        f"- confidence_threshold_implemented: `{report.get('confidence_threshold_implemented')}`",
        f"- not_for_decision: `{report.get('not_for_decision')}`",
        "",
        "## Verifier / Rule calibration (existing signals → progress)",
        "",
    ]
    for title, key, left in (
        ("Verifier confidence label → progress_action", "verifier_label_vs_progress", "verify_confidence_label"),
        ("Evidence level → progress_action", "evidence_level_vs_progress", "evidence_level"),
        ("Evidence level → case pass/fail", "evidence_level_vs_case_pass", "evidence_level"),
        ("Round had verify ok → progress_action", "round_had_verify_ok_vs_progress", "had_verify_ok"),
        ("Judge satisfies → progress_action", "judge_satisfies_vs_progress", "judge_satisfies"),
        ("no_gain → progress_action", "no_gain_vs_progress", "no_gain"),
    ):
        lines.append(f"### {title}")
        lines.append("")
        rows = agg.get(key) or []
        if not rows:
            lines.append("- (no data)")
            lines.append("")
            continue
        for row in rows:
            rates = row.get("outcome_rates") or {}
            rate_s = ", ".join(f"{k}={v}" for k, v in rates.items())
            lines.append(
                f"- `{row.get(left)}` n={row.get('n')}: {rate_s}"
            )
        lines.append("")

    lines.extend(
        [
            "## Web evidence ↔ decision linkage audit",
            "",
            f"- rounds_total: {web.get('rounds_total')}",
            f"- rounds_with_hits: {web.get('rounds_with_hits')}",
            f"- candidates_total (verified_runs / keys linked): {web.get('candidates_total')}",
            f"- candidates_linked (token_overlap>0): {web.get('candidates_linked')}",
            f"- link_coverage: {web.get('link_coverage')}",
            f"- hit_score_present_saved (KSS-1.1): {web.get('hit_score_present_saved')}",
            f"- hit_score_missing_saved (KSS-1.1): {web.get('hit_score_missing_saved')}",
            f"- hit_score_computed_retro: {web.get('hit_score_computed_retro')}",
            f"- audit_gaps: `{json.dumps(web.get('audit_gaps') or {}, ensure_ascii=False)}`",
            f"- overlap_hist: `{json.dumps(web.get('overlap_hist') or {}, ensure_ascii=False)}`",
            "",
            f"> {web.get('note') or ''}",
            "",
            "## Code linkage (static)",
            "",
        ]
    )
    for k, v in (report.get("code_linkage_audit") or {}).items():
        lines.append(f"- `{k}`: `{v}`")
    lines.extend(
        [
            "",
            "## Recommendations (no thresholds yet)",
            "",
            "1. Treat existing verifier `high/low` + progress rule as the primary calibration spine.",
            "2. Do **not** introduce routing or confidence cutoffs until link_coverage and label→outcome tables stabilize across more trials.",
            "3. For future live runs, enable `AI_AGENT_KSS12_OBS` so `web_hits[].score` and candidate↔hit links are stored (behavior unchanged).",
            "4. Hard FK (`candidate.hit_url`) remains optional; only add if overlap audit stays weak.",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exp-dir",
        default=str(
            ROOT
            / "research"
            / "llm_benchmarks"
            / "kss11_measurement"
            / "kss11_20260820_151041"
        ),
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    exp_dir = Path(args.exp_dir)
    report = calibrate_experiment_dir(exp_dir)
    out_dir = Path(args.out_dir) if args.out_dir else exp_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "kss12_calibration.json"
    out_md = out_dir / "kss12_report.md"
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report_md(report, out_md)
    print(json.dumps(report.get("aggregate"), ensure_ascii=False, indent=2))
    print(f"\nWrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
