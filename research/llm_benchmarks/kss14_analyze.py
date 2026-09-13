"""
KSS-1.4: Research 経路分解・情報喪失点・discarded hit 答え存在性の分析。
observation-only。routing しない。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from tools.ai.state.information_loss import build_trajectory
from tools.ai.state.web_answer_presence import (
    MISSING,
    audit_round_answer_presence,
)

ROOT = Path(__file__).resolve().parents[2]


def _num(v):
    if v is None or v == MISSING or v == "missing":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _add_counts(dst, src):
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if k.startswith("discard_"):
            continue
        n = _num(v)
        if n is None:
            continue
        dst[k] = dst.get(k, 0) + n


def load_case(path: Path):
    rec = json.loads(path.read_text(encoding="utf-8"))
    pipe = rec.get("pipeline") or {}
    metrics = rec.get("metrics") or {}
    case = rec.get("case")
    request = rec.get("request") or ""
    details = pipe.get("research_rounds_detail") or []
    k13 = [
        d.get("exploration_value_observation")
        for d in details
        if isinstance(d.get("exploration_value_observation"), dict)
        and d["exploration_value_observation"].get("enabled")
    ]
    traj = pipe.get("information_loss_trajectory")
    if not isinstance(traj, dict) or not traj.get("rounds"):
        traj = build_trajectory(
            case_id=case,
            rounds_kss13=k13 or None,
            round_details=details,
            final_pass=metrics.get("pass", rec.get("pass")),
            fail_stage=metrics.get("fail_stage", rec.get("fail_stage")),
            fail_reason=rec.get("error")
            or (pipe.get("research") or {}).get("stop_reason"),
            stop_reason=(pipe.get("research") or {}).get("stop_reason"),
            research_run_id=path.parent.name,
        )

    # ensure answer presence on each round
    answer_rounds = []
    for item in details:
        loss = item.get("information_loss_observation") or {}
        audit = loss.get("web_answer_presence_audit") if isinstance(loss, dict) else None
        if not isinstance(audit, dict) or not audit.get("enabled"):
            audit = audit_round_answer_presence(
                request_text=request,
                case_id=case,
                web_hit_partition=item.get("web_hit_partition"),
                round_item=item,
            )
            if isinstance(loss, dict) and loss.get("enabled"):
                loss["web_answer_presence_audit"] = audit
                item["information_loss_observation"] = loss
        answer_rounds.append(audit)

    # run-level answer aggregates
    run_agg = Counter()
    human_samples = []
    lead_then_next_gain = {"lead_rounds": 0, "next_gain_true": 0, "next_gain_false": 0, "next_gain_missing": 0}
    for i, audit in enumerate(answer_rounds):
        if not isinstance(audit, dict):
            continue
        ag = audit.get("aggregates") or {}
        for key in (
            "total_web_hits",
            "kept_hits",
            "dropped_hits",
            "direct_in_kept",
            "core_in_kept",
            "lead_in_kept",
            "direct_in_dropped",
            "core_in_dropped",
            "lead_in_dropped",
            "unknown_count",
        ):
            n = _num(ag.get(key))
            if n is not None:
                run_agg[key] += n
        for sample in audit.get("human_audit_samples") or []:
            if sample.get("status") == "missing":
                continue
            human_samples.append(sample)
        # lead → next round gain
        if audit.get("lead_present") is True:
            lead_then_next_gain["lead_rounds"] += 1
            rounds = traj.get("rounds") or []
            if i < len(rounds):
                ng = rounds[i].get("next_round_gain")
                if ng is True:
                    lead_then_next_gain["next_gain_true"] += 1
                elif ng is False:
                    lead_then_next_gain["next_gain_false"] += 1
                else:
                    lead_then_next_gain["next_gain_missing"] += 1

    answer_in_dropped = any(
        (a.get("aggregates") or {}).get("answer_in_dropped_hit") is True
        for a in answer_rounds
        if isinstance(a, dict)
    )
    answer_in_kept = any(
        (a.get("aggregates") or {}).get("answer_in_kept_hit") is True
        for a in answer_rounds
        if isinstance(a, dict)
    )
    dropped_known = any(
        (a.get("aggregates") or {}).get("dropped_hits") not in (None, MISSING, "missing")
        for a in answer_rounds
        if isinstance(a, dict)
    )
    # valuable dropped & not kept
    valuable_only_dropped = any(
        (a.get("aggregates") or {}).get("valuable_dropped_not_kept") is True
        for a in answer_rounds
        if isinstance(a, dict)
    )

    return {
        "case": case,
        "pass": metrics.get("pass", rec.get("pass")),
        "fail_stage": metrics.get("fail_stage", rec.get("fail_stage")),
        "stop_reason": (pipe.get("research") or {}).get("stop_reason"),
        "trajectory": traj,
        "answer_run": {
            "aggregates_sum": dict(run_agg),
            "answer_in_kept_hit": answer_in_kept,
            "answer_in_dropped_hit": answer_in_dropped
            if dropped_known
            else "missing",
            "valuable_only_in_dropped": valuable_only_dropped
            if dropped_known
            else "missing",
            "dropped_hits_observed": dropped_known,
            "lead_then_next_gain": lead_then_next_gain,
        },
        "human_audit_samples": human_samples[:12],
        "file": path.name,
    }


def signal_vs_outcome(cases, signal_fn):
    """signal present/absent × eventual success/fail / next_round_gain."""
    rows = Counter()
    for case in cases:
        success = case.get("pass") is True
        for rnd in (case.get("trajectory") or {}).get("rounds") or []:
            present = signal_fn(rnd)
            if present is None:
                continue
            key = (
                "signal_yes" if present else "signal_no",
                "success" if success else "fail",
            )
            rows[key] += 1
            ng = rnd.get("next_round_gain")
            if ng is True or ng is False:
                rows[
                    (
                        "signal_yes" if present else "signal_no",
                        "next_gain" if ng else "next_no_gain",
                    )
                ] += 1
    return {f"{a}|{b}": n for (a, b), n in rows.items()}


def analyze_experiment_dir(exp_dir: Path):
    cases = []
    for path in sorted(Path(exp_dir).glob("*.json")):
        if path.name in ("summary.json", "manifest.json"):
            continue
        try:
            cases.append(load_case(path))
        except Exception as exc:
            cases.append({"case": path.name, "error": str(exc)})

    success = [c for c in cases if c.get("pass") is True]
    fail = [c for c in cases if c.get("pass") is False]

    # answer presence rollup
    totals = Counter()
    for c in cases:
        _add_counts(totals, (c.get("answer_run") or {}).get("aggregates_sum") or {})

    failed_with_answer_dropped = sum(
        1
        for c in fail
        if (c.get("answer_run") or {}).get("answer_in_dropped_hit") is True
    )
    failed_with_answer_kept = sum(
        1
        for c in fail
        if (c.get("answer_run") or {}).get("answer_in_kept_hit") is True
    )
    failed_no_answer = sum(
        1
        for c in fail
        if (c.get("answer_run") or {}).get("answer_in_kept_hit") is False
        and (c.get("answer_run") or {}).get("answer_in_dropped_hit")
        in (False, "missing")
    )

    # Q1: fail with kept hits
    fail_with_hits = 0
    fail_without_hits = 0
    for c in fail:
        rounds = (c.get("trajectory") or {}).get("rounds") or []
        if any((_num(r.get("hit")) or 0) > 0 for r in rounds):
            fail_with_hits += 1
        else:
            fail_without_hits += 1

    # kept valuable but no usable
    kept_valuable_no_usable = 0
    cand_no_usable = 0
    for c in fail:
        for r in (c.get("trajectory") or {}).get("rounds") or []:
            if (_num(r.get("candidate")) or 0) > 0 and (_num(r.get("usable")) or 0) == 0:
                cand_no_usable += 1
        if (c.get("answer_run") or {}).get("answer_in_kept_hit") is True:
            # check usable across traj
            if not any(
                (_num(r.get("usable")) or 0) > 0
                for r in (c.get("trajectory") or {}).get("rounds") or []
            ):
                kept_valuable_no_usable += 1

    # link_coverage=0 success (memory contrast)
    success_no_link = sum(
        1
        for c in success
        if any(
            (_num(r.get("link_coverage")) == 0)
            for r in (c.get("trajectory") or {}).get("rounds") or []
        )
    )

    # no_gain preceded by lead/novelty
    gain_before_no_gain = 0
    for c in cases:
        rounds = (c.get("trajectory") or {}).get("rounds") or []
        saw_leadish = False
        for r in rounds:
            if (_num(r.get("new_term")) or 0) > 0 or (_num(r.get("new_source")) or 0) > 0:
                saw_leadish = True
            if saw_leadish and r.get("no_gain") is True:
                gain_before_no_gain += 1
                break

    comparisons = {
        "hit_present": signal_vs_outcome(
            cases, lambda r: (_num(r.get("hit")) or 0) > 0
        ),
        "new_source": signal_vs_outcome(
            cases, lambda r: (_num(r.get("new_source")) or 0) > 0
        ),
        "new_term": signal_vs_outcome(
            cases, lambda r: (_num(r.get("new_term")) or 0) > 0
        ),
        "candidate": signal_vs_outcome(
            cases, lambda r: (_num(r.get("candidate")) or 0) > 0
        ),
        "linked": signal_vs_outcome(
            cases, lambda r: (_num(r.get("linked")) or 0) > 0
        ),
        "no_gain": signal_vs_outcome(cases, lambda r: r.get("no_gain") is True),
    }

    label_dist = Counter()
    first_losses = []
    for c in cases:
        for lab in (
            (c.get("trajectory") or {}).get("run_loss_classification") or {}
        ).get("labels") or []:
            label_dist[lab] += 1
        fl = (
            (c.get("trajectory") or {}).get("run_loss_classification") or {}
        ).get("first_loss_in_run")
        if fl:
            first_losses.append({"case": c.get("case"), **fl})

    focus = {}
    for name in ("cpu_temperature", "disk_usage", "gpu_vram_usage", "memory_usage"):
        match = next((c for c in cases if c.get("case") == name), None)
        if not match:
            continue
        focus[name] = {
            "pass": match.get("pass"),
            "fail_stage": match.get("fail_stage"),
            "stop_reason": match.get("stop_reason"),
            "labels": (
                (match.get("trajectory") or {}).get("run_loss_classification") or {}
            ).get("labels"),
            "first_loss": (
                (match.get("trajectory") or {}).get("run_loss_classification") or {}
            ).get("first_loss_in_run"),
            "web_vs_llm": (match.get("trajectory") or {}).get("web_vs_llm_run_labels"),
            "trajectory_rounds": (match.get("trajectory") or {}).get("rounds"),
            "answer_run": match.get("answer_run"),
        }

    questions = {
        "Q1_fail_despite_web_hits": {
            "fail_with_hits": fail_with_hits,
            "fail_without_hits": fail_without_hits,
            "note": "tendency only; n small",
        },
        "Q2_hit_vs_success_rate": comparisons["hit_present"],
        "Q3_new_source_term_then_gain": {
            "new_source": comparisons["new_source"],
            "new_term": comparisons["new_term"],
            "lead_then_next_gain": [
                (c.get("case"), (c.get("answer_run") or {}).get("lead_then_next_gain"))
                for c in cases
            ],
        },
        "Q4_candidate_without_usable": {"round_count": cand_no_usable},
        "Q5_success_without_link": {
            "success_cases_with_link_coverage_0": success_no_link,
            "contrast": "memory_usage may succeed without linkage",
        },
        "Q6_no_gain_after_useful_exploration": {
            "cases_with_novelty_before_no_gain": gain_before_no_gain
        },
        "Q7_first_loss_points": first_losses,
        "Q8_trajectory_success_vs_fail": {
            "success_avg_rounds": (
                sum(len((c.get("trajectory") or {}).get("rounds") or []) for c in success)
                / len(success)
                if success
                else None
            ),
            "fail_avg_rounds": (
                sum(len((c.get("trajectory") or {}).get("rounds") or []) for c in fail)
                / len(fail)
                if fail
                else None
            ),
        },
    }

    answer_questions = {
        "A1_failures_without_web_answer": failed_no_answer,
        "A2_failures_with_answer_only_in_dropped": failed_with_answer_dropped,
        "A3_lead_presence": totals.get("lead_in_kept", 0) + totals.get("lead_in_dropped", 0),
        "A4_lead_then_additional_info": [
            (c.get("case"), (c.get("answer_run") or {}).get("lead_then_next_gain"))
            for c in cases
        ],
        "A5_valuable_in_dropped": {
            "direct_in_dropped": totals.get("direct_in_dropped", 0),
            "core_in_dropped": totals.get("core_in_dropped", 0),
            "lead_in_dropped": totals.get("lead_in_dropped", 0),
            "dropped_observed": any(
                (c.get("answer_run") or {}).get("dropped_hits_observed") for c in cases
            ),
            "note": (
                "If dropped_hits missing on historical data, counts stay 0/"
                "missing — do not invent."
            ),
        },
        "A6_kept_valuable_but_no_usable": kept_valuable_no_usable,
        "A7_loss_label_distribution": dict(label_dist),
    }

    routing_ready = {
        "sufficient_for_routing_rules": False,
        "reason": (
            "n small; dropped_hits often missing on historical runs; "
            "heuristic answer_presence not calibrated vs human; "
            "no causal proof that continuing web would flip fail→pass."
        ),
        "next_observations": [
            "Live KSS-1.4 runs with web_hit_partition (kept+dropped)",
            "Human audit of heuristic vs human_answer_presence samples",
            "Optional offline web_answer_presence_judge (LLM) agreement rate",
            "More success trajectories beyond memory_usage",
        ],
        "options_not_executed": {
            "A": "Webを追加探索",
            "B": "検索戦略を変更",
            "C": "LLMに戻す",
            "D": "上位LLMへ相談",
            "E": "HELP",
            "F": "終了",
        },
    }

    return {
        "phase": "kss-1.4",
        "experiment_dir": str(exp_dir),
        "not_for_decision": True,
        "routing_implemented": False,
        "case_count": len(cases),
        "success_count": len(success),
        "fail_count": len(fail),
        "answer_presence_totals": {
            **dict(totals),
            "failed_runs_with_answer_in_dropped_hit": failed_with_answer_dropped,
            "failed_runs_with_answer_in_kept_hit": failed_with_answer_kept,
            "failed_runs_with_no_answer_found": failed_no_answer,
        },
        "focus_cases": focus,
        "questions": questions,
        "answer_presence_questions": answer_questions,
        "signal_comparisons": comparisons,
        "human_audit_samples": [
            s for c in cases for s in (c.get("human_audit_samples") or [])
        ][:40],
        "per_case": [
            {
                "case": c.get("case"),
                "pass": c.get("pass"),
                "fail_stage": c.get("fail_stage"),
                "stop_reason": c.get("stop_reason"),
                "labels": (
                    (c.get("trajectory") or {}).get("run_loss_classification") or {}
                ).get("labels"),
                "first_loss": (
                    (c.get("trajectory") or {}).get("run_loss_classification") or {}
                ).get("first_loss_in_run"),
                "trajectory": (c.get("trajectory") or {}).get("rounds"),
                "answer_run": c.get("answer_run"),
                "error": c.get("error"),
            }
            for c in cases
        ],
        "routing_readiness": routing_ready,
        "kss15_hypotheses": [
            "H-A: valuable dropped hits (direct/core/lead) correlate with avoidable failures",
            "H-B: lead rounds predict next_round novelty more than raw hit counts",
            "H-C: verification/judge gaps dominate when kept already has core",
            "H-D: search-strategy change beats blind additional searches",
        ],
    }


def write_report(summary: dict, out_path: Path):
    ap = summary.get("answer_presence_totals") or {}
    lines = [
        "# KSS-1.4 Information Loss & Discarded-Hit Answer Audit",
        "",
        f"- experiment_dir: `{summary.get('experiment_dir')}`",
        f"- cases: {summary.get('case_count')} (success={summary.get('success_count')}, fail={summary.get('fail_count')})",
        f"- routing_implemented: `{summary.get('routing_implemented')}`",
        f"- not_for_decision: `{summary.get('not_for_decision')}`",
        "",
        "## Answer presence totals",
        "",
        f"- total_web_hits (sum over annotated): {ap.get('total_web_hits')}",
        f"- kept_hits: {ap.get('kept_hits')}",
        f"- dropped_hits: {ap.get('dropped_hits')}",
        f"- direct/core/lead in kept: {ap.get('direct_in_kept')}/{ap.get('core_in_kept')}/{ap.get('lead_in_kept')}",
        f"- direct/core/lead in dropped: {ap.get('direct_in_dropped')}/{ap.get('core_in_dropped')}/{ap.get('lead_in_dropped')}",
        f"- unknown_count: {ap.get('unknown_count')}",
        f"- failed_runs_with_answer_in_dropped_hit: {ap.get('failed_runs_with_answer_in_dropped_hit')}",
        f"- failed_runs_with_answer_in_kept_hit: {ap.get('failed_runs_with_answer_in_kept_hit')}",
        f"- failed_runs_with_no_answer_found: {ap.get('failed_runs_with_no_answer_found')}",
        "",
        "> Historical KSS-1.1/1.3 JSON usually lack `dropped_hits` → dropped_* may be missing/0. Live `web_hit_partition` fixes this.",
        "",
        "## Focus trajectories",
        "",
    ]
    for name, data in (summary.get("focus_cases") or {}).items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(
            f"- pass={data.get('pass')} fail_stage={data.get('fail_stage')} "
            f"stop={data.get('stop_reason')}"
        )
        lines.append(f"- labels: {data.get('labels')}")
        lines.append(f"- first_loss: {data.get('first_loss')}")
        lines.append(f"- web_vs_llm: {data.get('web_vs_llm')}")
        lines.append(f"- answer_run: `{json.dumps(data.get('answer_run'), ensure_ascii=False)}`")
        lines.append("")
        for r in data.get("trajectory_rounds") or []:
            lines.append(
                f"  - r{r.get('round_index')}: hit={r.get('hit')} cand={r.get('candidate')} "
                f"linked={r.get('linked')} usable={r.get('usable')} "
                f"gain={r.get('gain')} no_gain={r.get('no_gain')} "
                f"new_term={r.get('new_term')} action={r.get('progress_action')}/"
                f"{r.get('progress_reason')} loss={r.get('first_loss_point')}"
            )
        lines.append("")

    lines.extend(["## Report questions (tendency only)", ""])
    for k, v in (summary.get("questions") or {}).items():
        lines.append(f"### {k}")
        lines.append("")
        lines.append(f"```json\n{json.dumps(v, ensure_ascii=False, indent=2)}\n```")
        lines.append("")

    lines.extend(["## Answer-presence questions", ""])
    for k, v in (summary.get("answer_presence_questions") or {}).items():
        lines.append(f"### {k}")
        lines.append("")
        lines.append(f"```json\n{json.dumps(v, ensure_ascii=False, indent=2)}\n```")
        lines.append("")

    lines.extend(
        [
            "## Human audit samples (fill human_answer_presence)",
            "",
            "Heuristic labels are **not** ground truth. Compare before trusting "
            "`web_answer_presence_judge` (LLM).",
            "",
        ]
    )
    for i, s in enumerate((summary.get("human_audit_samples") or [])[:20], 1):
        lines.append(
            f"{i}. [{s.get('bucket')}] case={s.get('case_id')} "
            f"heuristic={s.get('heuristic_answer_presence')} "
            f"discard={s.get('discard_reason')}"
        )
        lines.append(f"   - title: {s.get('title')}")
        lines.append(f"   - url: {s.get('url')}")
        lines.append(f"   - snippet: {(s.get('snippet') or '')[:180]}")
        lines.append(
            f"   - human_answer_presence: {s.get('human_answer_presence')} "
            f"(fill: direct|core|lead|related|none|unknown)"
        )
        lines.append("")

    rr = summary.get("routing_readiness") or {}
    lines.extend(
        [
            "## Routing readiness",
            "",
            f"- sufficient_for_routing_rules: **{rr.get('sufficient_for_routing_rules')}**",
            f"- reason: {rr.get('reason')}",
            f"- next_observations: {rr.get('next_observations')}",
            f"- options_not_executed: {rr.get('options_not_executed')}",
            "",
            "## KSS-1.5 hypotheses to test next",
            "",
        ]
    )
    for h in summary.get("kss15_hypotheses") or []:
        lines.append(f"- {h}")
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-dir", required=True)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    exp_dir = Path(args.exp_dir)
    out_dir = Path(args.out_dir) if args.out_dir else exp_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = analyze_experiment_dir(exp_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(summary, out_dir / "report.md")
    print(f"Wrote {out_dir / 'summary.json'}")
    print(f"Wrote {out_dir / 'report.md'}")
    print(
        "routing_ready:",
        (summary.get("routing_readiness") or {}).get("sufficient_for_routing_rules"),
    )


if __name__ == "__main__":
    main()
