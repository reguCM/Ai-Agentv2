"""
KSS-1.3: 探索価値観測の集計・レポート生成。

成功/失敗比較、仮説1〜5の暫定評価。統計的結論はサンプル不足時に出さない。
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from tools.ai.state.exploration_value import rebuild_from_round_details

ROOT = Path(__file__).resolve().parents[2]
MISSING = "missing"


def _num(v):
    if v is None or v == MISSING:
        return None
    if isinstance(v, bool):
        return int(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _avg(vals):
    xs = [x for x in vals if x is not None]
    if not xs:
        return None
    return round(sum(xs) / len(xs), 3)


def _dist(vals):
    xs = [x for x in vals if x is not None]
    if not xs:
        return {"n": 0, "avg": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "avg": round(sum(xs) / len(xs), 3),
        "min": min(xs),
        "max": max(xs),
        "median": round(statistics.median(xs), 3) if len(xs) >= 1 else None,
    }


def classify_path_abcd(bundles):
    """
    A: 最初から情報がほとんど増えていない
    B: 途中まで増えた後 stagnation
    C: Web hit あるが candidate 接続失敗
    D: candidate あるが核心（usable/implement）に未到達
    E: 検索は有望だが judge/LLM 側で未利用（proxy）
    """
    if not bundles:
        return {"labels": ["no_rounds"], "notes": ["zero research rounds"]}

    nov_urls = [b.get("information_novelty", {}).get("new_url_count") or 0 for b in bundles]
    nov_terms = [b.get("information_novelty", {}).get("new_term_count") or 0 for b in bundles]
    early = bundles[: max(1, len(bundles) // 3)]
    late = bundles[max(1, len(bundles) // 3) :]
    early_gain = sum(
        (b.get("information_novelty", {}).get("new_term_count") or 0)
        + (b.get("information_novelty", {}).get("new_url_count") or 0)
        for b in early
    )
    late_gain = sum(
        (b.get("information_novelty", {}).get("new_term_count") or 0)
        + (b.get("information_novelty", {}).get("new_url_count") or 0)
        for b in late
    )

    labels = []
    notes = []
    if sum(nov_urls) + sum(nov_terms) <= 2 and len(bundles) >= 3:
        labels.append("A_little_info_growth")
        notes.append("cumulative new_url+new_term very low across rounds")
    if early_gain > 0 and late_gain == 0 and len(bundles) >= 3:
        labels.append("B_early_gain_then_stagnation")
        notes.append("novelty concentrated early; late rounds flat")

    hits = sum(
        (b.get("search_volume") or {}).get("kept_hit_count") or 0 for b in bundles
    )
    linked = sum(
        _num((b.get("exploration_leads") or {}).get("linked_candidate_count")) or 0
        for b in bundles
    )
    cands = sum(
        _num((b.get("exploration_leads") or {}).get("candidate_count")) or 0
        for b in bundles
    )
    zero = sum(
        _num((b.get("exploration_leads") or {}).get("zero_overlap_count")) or 0
        for b in bundles
    )
    if hits > 0 and (linked == 0 or zero >= max(1, cands // 2)):
        labels.append("C_hits_but_weak_candidate_link")
        notes.append("kept hits present but candidate↔hit linkage weak")

    usable = sum(
        _num((b.get("evidence_strength") or {}).get("usable_count")) or 0
        for b in bundles
    )
    implement = any(b.get("progress_action") == "implement" for b in bundles)
    if cands > 0 and usable == 0 and not implement:
        labels.append("D_candidates_without_core_usable")
        notes.append("candidates generated but no usable/implement")

    judge_false = 0
    for b in bundles:
        # from evidence if present — not always on kss13 bundle
        pass
    # proxy E: evidence_level medium+ with progress continue/stop and no implement
    strong = any(
        (b.get("evidence_strength") or {}).get("evidence_level") in ("high", "medium")
        for b in bundles
    )
    if strong and not implement and hits > 0:
        labels.append("E_promising_web_unused_by_judge_proxy")
        notes.append(
            "proxy: medium/high evidence_level or hits but never implement "
            "(judge/LLM utilization gap not proven)"
        )

    if not labels:
        if implement:
            labels.append("success_path_or_quick_implement")
        else:
            labels.append("unclassified")
    return {"labels": labels, "notes": notes}


def load_case_record(path: Path):
    rec = json.loads(path.read_text(encoding="utf-8"))
    pipe = rec.get("pipeline") or {}
    metrics = rec.get("metrics") or {}
    live = pipe.get("exploration_value_rounds")
    if live:
        bundles = live
    else:
        bundles = rebuild_from_round_details(
            pipe.get("research_rounds_detail") or [],
            progress_log=pipe.get("progress") or [],
            case_id=rec.get("case"),
            research_run_id=rec.get("experiment_id")
            or (rec.get("experiment") or {}).get("AI_AGENT_EXPERIMENT_ID"),
            final_pass=metrics.get("pass", rec.get("pass")),
            fail_stage=metrics.get("fail_stage", rec.get("fail_stage")),
            fail_reason=rec.get("error")
            or (pipe.get("research") or {}).get("stop_reason"),
        )
    return {
        "case": rec.get("case"),
        "pass": metrics.get("pass", rec.get("pass")),
        "fail_stage": metrics.get("fail_stage", rec.get("fail_stage")),
        "rounds": len(bundles),
        "stop_reason": (pipe.get("research") or {}).get("stop_reason"),
        "bundles": bundles,
        "path_class": classify_path_abcd(bundles),
        "file": path.name,
    }


def summarize_group(cases):
    metrics = defaultdict(list)
    for case in cases:
        for b in case["bundles"]:
            sv = b.get("search_volume") or {}
            nov = b.get("information_novelty") or {}
            lead = b.get("exploration_leads") or {}
            metrics["search_result_count"].append(_num(sv.get("search_result_count")))
            metrics["kept_hit_count"].append(_num(sv.get("kept_hit_count")))
            metrics["new_source_count"].append(_num(nov.get("new_source_count")))
            metrics["new_term_count"].append(_num(nov.get("new_term_count")))
            metrics["new_url_count"].append(_num(nov.get("new_url_count")))
            metrics["candidate_count"].append(_num(lead.get("candidate_count")))
            metrics["link_coverage"].append(_num(lead.get("link_coverage")))
            metrics["zero_overlap_count"].append(_num(lead.get("zero_overlap_count")))
            ng = b.get("no_gain_existing")
            metrics["no_gain"].append(
                1.0 if ng is True else (0.0 if ng is False else None)
            )
            ig = b.get("information_gain_existing")
            if isinstance(ig, dict):
                metrics["information_gain"].append(
                    1.0 if ig.get("has_gain") else 0.0
                )
            else:
                metrics["information_gain"].append(None)
        metrics["rounds_per_case"].append(float(case["rounds"]))

    return {k: _dist(v) for k, v in metrics.items()}


def evaluate_hypotheses(success_cases, fail_cases, all_cases):
    """暫定評価。n が小さいときは established=False。"""
    s = summarize_group(success_cases)
    f = summarize_group(fail_cases)
    n_s, n_f = len(success_cases), len(fail_cases)
    small = (n_s + n_f) < 8

    def trend(metric, higher_for_success=True):
        sa = (s.get(metric) or {}).get("avg")
        fa = (f.get(metric) or {}).get("avg")
        if sa is None or fa is None:
            return {
                "status": "insufficient_data",
                "success_avg": sa,
                "fail_avg": fa,
                "established": False,
            }
        if higher_for_success:
            direction = "supports_trend" if sa > fa else "opposes_trend"
        else:
            direction = "supports_trend" if sa < fa else "opposes_trend"
        return {
            "status": direction,
            "success_avg": sa,
            "fail_avg": fa,
            "established": False if small else direction == "supports_trend",
            "note": "sample_small" if small else None,
        }

    # H2: rounds with exploration leads → later success
    lead_then_success = 0
    lead_then_fail = 0
    for case in all_cases:
        bundles = case["bundles"]
        for i, b in enumerate(bundles[:-1]):
            lead = b.get("exploration_signal") or {}
            has_lead = bool(
                lead.get("has_new_term")
                or lead.get("has_new_source")
                or lead.get("has_new_url")
            )
            if not has_lead:
                continue
            if case["pass"]:
                lead_then_success += 1
            else:
                lead_then_fail += 1

    # H3/H4: consecutive novelty / no_gain streaks vs stop
    return {
        "H1_external_research_value_when_llm_hard": {
            "status": "observational_only",
            "note": (
                "Requires cases labeled LLM-hard; proxy=fail with many rounds. "
                "Not established."
            ),
            "fail_cases_with_rounds_ge_5": sum(
                1 for c in fail_cases if c["rounds"] >= 5
            ),
            "established": False,
        },
        "H2_exploration_leads_predict_later_success": {
            "lead_round_in_success_runs": lead_then_success,
            "lead_round_in_fail_runs": lead_then_fail,
            "established": False,
            "note": "counts are co-occurrence not causal; sample limited",
        },
        "H3_continue_while_novelty_arrives": trend("new_term_count", True),
        "H4_no_gain_streak_lowers_value": trend("no_gain", False),
        "H5_novelty_and_linkage_beat_hit_count": {
            "kept_hit_count": trend("kept_hit_count", True),
            "new_source_count": trend("new_source_count", True),
            "new_term_count": trend("new_term_count", True),
            "link_coverage": trend("link_coverage", True),
            "established": False,
            "note": "compare which metric separates success/fail more; n small",
        },
    }


def analyze_experiment_dir(exp_dir: Path):
    cases = []
    for path in sorted(exp_dir.glob("*.json")):
        if path.name in ("summary.json", "manifest.json"):
            continue
        if "report" in path.name:
            continue
        try:
            cases.append(load_case_record(path))
        except Exception as exc:
            cases.append({"case": path.name, "error": str(exc), "bundles": []})

    success = [c for c in cases if c.get("pass") is True]
    fail = [c for c in cases if c.get("pass") is False]
    other = [c for c in cases if c.get("pass") not in (True, False)]

    summary = {
        "phase": "kss-1.3",
        "experiment_dir": str(exp_dir),
        "not_for_decision": True,
        "routing_implemented": False,
        "confidence_threshold_implemented": False,
        "case_count": len(cases),
        "success_count": len(success),
        "fail_count": len(fail),
        "other_count": len(other),
        "per_case": [
            {
                "case": c.get("case"),
                "pass": c.get("pass"),
                "fail_stage": c.get("fail_stage"),
                "rounds": c.get("rounds"),
                "stop_reason": c.get("stop_reason"),
                "path_class": c.get("path_class"),
                "round_snapshots": [
                    {
                        "round_index": b.get("round_index"),
                        "kept_hit_count": (b.get("search_volume") or {}).get(
                            "kept_hit_count"
                        ),
                        "search_result_count": (b.get("search_volume") or {}).get(
                            "search_result_count"
                        ),
                        "new_source_count": (b.get("information_novelty") or {}).get(
                            "new_source_count"
                        ),
                        "new_term_count": (b.get("information_novelty") or {}).get(
                            "new_term_count"
                        ),
                        "new_url_count": (b.get("information_novelty") or {}).get(
                            "new_url_count"
                        ),
                        "candidate_count": (b.get("exploration_leads") or {}).get(
                            "candidate_count"
                        ),
                        "link_coverage": (b.get("exploration_leads") or {}).get(
                            "link_coverage"
                        ),
                        "zero_overlap_count": (b.get("exploration_leads") or {}).get(
                            "zero_overlap_count"
                        ),
                        "no_gain_existing": b.get("no_gain_existing"),
                        "information_gain_existing": b.get(
                            "information_gain_existing"
                        ),
                        "progress_action": b.get("progress_action"),
                        "progress_reason": b.get("progress_reason"),
                        "exploration_signal": b.get("exploration_signal"),
                    }
                    for b in (c.get("bundles") or [])
                ],
                "error": c.get("error"),
            }
            for c in cases
        ],
        "compare_success_vs_failure": {
            "success": summarize_group(success),
            "failure": summarize_group(fail),
            "sample_note": (
                "n is small; treat as tendency only, not established relation"
                if len(success) + len(fail) < 8
                else "still observational; no causal claim"
            ),
        },
        "hypotheses": evaluate_hypotheses(success, fail, success + fail),
        "missing_fields_common": [
            "search_result_count (offline / no web_exec)",
            "new_entity_count",
            "exploration_value_score (intentionally not created)",
            "semantic_novelty",
        ],
    }
    return summary


def write_report(summary: dict, out_path: Path):
    lines = [
        "# KSS-1.3 Exploration Value Observation Report",
        "",
        f"- experiment_dir: `{summary.get('experiment_dir')}`",
        f"- cases: {summary.get('case_count')} (success={summary.get('success_count')}, fail={summary.get('fail_count')})",
        f"- routing_implemented: `{summary.get('routing_implemented')}`",
        f"- confidence_threshold_implemented: `{summary.get('confidence_threshold_implemented')}`",
        f"- not_for_decision: `{summary.get('not_for_decision')}`",
        "",
        "## 1. Round-level exploration snapshots",
        "",
    ]
    for case in summary.get("per_case") or []:
        lines.append(
            f"### {case.get('case')} — pass={case.get('pass')} "
            f"rounds={case.get('rounds')} stop={case.get('stop_reason')} "
            f"path={case.get('path_class')}"
        )
        lines.append("")
        for snap in case.get("round_snapshots") or []:
            lines.append(
                f"- r{snap.get('round_index')}: kept={snap.get('kept_hit_count')} "
                f"search_raw={snap.get('search_result_count')} "
                f"new_src={snap.get('new_source_count')} "
                f"new_term={snap.get('new_term_count')} "
                f"cand={snap.get('candidate_count')} "
                f"link={snap.get('link_coverage')} "
                f"zero_ov={snap.get('zero_overlap_count')} "
                f"no_gain={snap.get('no_gain_existing')} "
                f"action={snap.get('progress_action')}/{snap.get('progress_reason')}"
            )
        lines.append("")

    lines.extend(["## 2. Success vs failure comparison", ""])
    cmp_ = summary.get("compare_success_vs_failure") or {}
    lines.append(f"> {cmp_.get('sample_note')}")
    lines.append("")
    for label in ("success", "failure"):
        lines.append(f"### {label}")
        lines.append("")
        for metric, dist in (cmp_.get(label) or {}).items():
            lines.append(
                f"- `{metric}`: n={dist.get('n')} avg={dist.get('avg')} "
                f"min={dist.get('min')} max={dist.get('max')} median={dist.get('median')}"
            )
        lines.append("")

    lines.extend(
        [
            "## 3. information_gain / no_gain relationship",
            "",
            "Existing `no_gain` / `information_gain` are copied as "
            "`no_gain_existing` / `information_gain_existing` (meaning unchanged).",
            "",
        ]
    )
    for case in summary.get("per_case") or []:
        ng = [
            s.get("no_gain_existing")
            for s in case.get("round_snapshots") or []
        ]
        lines.append(f"- {case.get('case')}: no_gain sequence={ng}")
    lines.append("")

    lines.extend(
        [
            "## 4. Web hit ↔ candidate linkage",
            "",
            "Uses KSS-1.2 token-overlap links (or retro). "
            "No hard FK `candidate.hit_url`.",
            "",
        ]
    )
    for case in summary.get("per_case") or []:
        links = [
            (s.get("round_index"), s.get("link_coverage"), s.get("zero_overlap_count"))
            for s in case.get("round_snapshots") or []
        ]
        lines.append(f"- {case.get('case')}: (round, link_coverage, zero_overlap)={links}")
    lines.append("")

    lines.extend(["## 5. Path to stagnation (A–E)", ""])
    for case in summary.get("per_case") or []:
        pc = case.get("path_class") or {}
        lines.append(
            f"- **{case.get('case')}**: {pc.get('labels')} — {pc.get('notes')}"
        )
    lines.append("")

    lines.extend(["## 6. Hypotheses (provisional)", ""])
    for key, val in (summary.get("hypotheses") or {}).items():
        lines.append(f"### {key}")
        lines.append("")
        lines.append(f"```json\n{json.dumps(val, ensure_ascii=False, indent=2)}\n```")
        lines.append("")

    lines.extend(
        [
            "## 7. Sample insufficiency / missing fields",
            "",
            f"- common missing: `{summary.get('missing_fields_common')}`",
            f"- case_count={summary.get('case_count')} → "
            "no established statistical claims",
            "",
            "## 8. Next-step proposals (still observation / no routing)",
            "",
            "1. Collect more trials with `AI_AGENT_KSS13_OBS=1` so "
            "`search_result_count` (web_exec) is live, not missing.",
            "2. Correlate `has_new_source/term` streaks with "
            "`next_round_gain` / eventual pass — still no threshold.",
            "3. Only after stable tables: consider "
            "`expected_next_search_value` model — not now.",
            "4. Do not add fixed search counts, Web force, or confidence routing.",
            "",
        ]
    )
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


if __name__ == "__main__":
    main()
