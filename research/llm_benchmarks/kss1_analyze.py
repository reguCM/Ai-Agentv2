"""
KSS-1 summary / 再分析。

新規 run: decision_confidence_observation から calibration を集計。
過去 run: confidence が無い場合は missing として扱い、0 に埋めない。
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from tools.ai.state.decision_confidence import (
    detect_high_confidence_stuck,
    reanalyze_past_runs_note,
    summarize_calibration,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"


def collect_from_run(run):
    pipe = run.get("pipeline") or {}
    rounds = pipe.get("research_rounds_detail") or []
    linked = []
    by_round = []
    obs_rounds = 0
    for item in rounds:
        obs = item.get("decision_confidence_observation") or {}
        if not obs.get("enabled"):
            continue
        obs_rounds += 1
        decisions = list(obs.get("decisions") or [])
        linked.extend(decisions)
        by_round.append({"round": item.get("round"), "decisions": decisions})
    return {
        "obs_rounds": obs_rounds,
        "linked_decisions": linked,
        "by_round": by_round,
        "stuck_events": detect_high_confidence_stuck(by_round),
        "calibration": summarize_calibration(linked),
    }


def analyze_results_path(path: Path, *, experiment_id=None):
    data = json.loads(path.read_text(encoding="utf-8"))
    runs = data.get("runs") or data.get("records") or []
    if isinstance(data, list):
        runs = data
    selected = []
    for run in runs:
        exp = run.get("experiment") or {}
        if experiment_id and exp.get("AI_AGENT_EXPERIMENT_ID") != experiment_id:
            continue
        selected.append(run)

    all_linked = []
    per_run = []
    missing_confidence_runs = 0
    for run in selected:
        info = collect_from_run(run)
        if info["obs_rounds"] == 0:
            missing_confidence_runs += 1
        all_linked.extend(info["linked_decisions"])
        per_run.append(
            {
                "timestamp": run.get("timestamp"),
                "request": run.get("request"),
                "pass": run.get("pass"),
                "fail_stage": run.get("fail_stage"),
                "obs_rounds": info["obs_rounds"],
                "calibration": info["calibration"],
                "stuck_events": info["stuck_events"],
            }
        )

    return {
        "n_runs": len(selected),
        "runs_without_kss1_obs": missing_confidence_runs,
        "past_reanalysis": reanalyze_past_runs_note(),
        "aggregate_calibration": summarize_calibration(all_linked),
        "stuck_events_total": sum(len(r.get("stuck_events") or []) for r in per_run),
        "per_run": per_run,
        "measurement_notes": {
            "missing_confidence_is_not_zero": True,
            "behavior_unchanged": True,
            "formalize_phase5_1": False,
        },
    }


def analyze_experiment_dir(exp_dir: Path):
    linked = []
    by_round = []
    files = sorted(exp_dir.glob("*.json"))
    for path in files:
        if path.name in ("summary.json", "manifest.json", "analysis.json"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        pipe = rec.get("pipeline") or {}
        for item in pipe.get("research_rounds_detail") or []:
            obs = item.get("decision_confidence_observation") or {}
            if not obs.get("enabled"):
                continue
            decisions = list(obs.get("decisions") or [])
            linked.extend(decisions)
            by_round.append({"round": item.get("round"), "decisions": decisions})
    return {
        "experiment_dir": str(exp_dir),
        "decisions": len(linked),
        "calibration": summarize_calibration(linked),
        "stuck_events": detect_high_confidence_stuck(by_round),
        "past_reanalysis": reanalyze_past_runs_note(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--exp-dir", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.exp_dir:
        report = analyze_experiment_dir(Path(args.exp_dir))
    else:
        report = analyze_results_path(
            Path(args.results), experiment_id=args.experiment_id
        )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
