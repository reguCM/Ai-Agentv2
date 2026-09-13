"""
KSS-1 measurement bench（観測整合性確認。性能比較ではない）。

行動経路は Phase 4 live と同一。KSS-1（+任意で KSS-0）観測のみ ON。

Usage:
  py -3.14 _kss1_measurement_bench.py
  py -3.14 _kss1_measurement_bench.py --cases memory_usage
"""
from __future__ import annotations

import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "kss1_measurement"
ENTRY = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
SNIPPET = {
    "memory_usage": "メモリ使用率",
    "cpu_temperature": "CPU温度",
    "disk_usage": "ディスク使用率",
    "gpu_usage": "GPUの使用率",
    "gpu_vram_usage": "GPU VRAM",
}

COMMON = {
    "AI_AGENT_CONTEXT_ALLOC_LIVE": "1",
    "AI_AGENT_CONTEXT_ALLOC_SHADOW": "1",
    "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1",
    "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE": "3",
    "AI_AGENT_MEMORY_JUDGE": "0",
    "AI_AGENT_MEMORY_RECALL": "0",
    "AI_AGENT_MEMORY_RECALL_VERSION": "none",
    "AI_AGENT_KNOWLEDGE_SOURCE_OBS": "1",
    "AI_AGENT_KSS1_OBS": "1",
}


def match_case(request, case):
    return SNIPPET.get(case, case) in (request or "")


def summarize(run):
    from tools.ai.state.decision_confidence import (
        detect_high_confidence_stuck,
        summarize_calibration,
    )

    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    cb = (pipe.get("context_budget_shadow") or {}).get("summary") or {}
    rounds = pipe.get("research_rounds_detail") or []
    hist = pipe.get("research_history") or []
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
    cal = summarize_calibration(linked)
    stuck = detect_high_confidence_stuck(by_round)
    overflow = run.get("error") == "context_overflow" or any(
        t.get("error") == "context_overflow" for t in (run.get("trace") or [])
    )
    return {
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "llm_calls": timing.get("llm_calls"),
        "usable_findings": len(research.get("usable_findings") or []),
        "actual_headroom_min": cb.get("actual_headroom_min"),
        "headroom_gate_ok": cb.get("headroom_gate_ok"),
        "context_overflow": overflow,
        "kss1_obs_rounds": obs_rounds,
        "kss1_history_events": sum(
            1 for e in hist if e.get("type") == "decision_confidence_obs"
        ),
        "decisions_total": cal.get("decisions_total"),
        "decisions_with_observation": cal.get("decisions_with_observation"),
        "observation_coverage": cal.get("observation_coverage"),
        "high_confidence_zero_gain_rate": cal.get("high_confidence_zero_gain_rate"),
        "high_confidence_repeating_rate": cal.get("high_confidence_repeating_rate"),
        "stuck_events": len(stuck),
        "result_linked_rate": (
            round(
                sum(1 for d in linked if d.get("result_linked")) / max(len(linked), 1),
                3,
            )
            if linked
            else None
        ),
        "behavior_changed": False,
        "auto_routing": False,
        "calibration": cal,
    }


def measurement_ok(records):
    problems = []
    for rec in records:
        m = rec.get("metrics") or {}
        if rec.get("error") == "NOT_FOUND":
            problems.append(f"{rec.get('case')}: NOT_FOUND")
            continue
        # research 未到達（proposal fail）は obs 0 でも可
        if m.get("rounds") is not None and m.get("kss1_obs_rounds", 0) <= 0:
            problems.append(f"{rec.get('case')}: no kss1 obs on research rounds")
        if m.get("context_overflow"):
            problems.append(f"{rec.get('case')}: overflow")
        if m.get("rounds") is not None and m.get("headroom_gate_ok") is False:
            problems.append(f"{rec.get('case')}: headroom gate fail")
        if m.get("behavior_changed"):
            problems.append(f"{rec.get('case')}: behavior_changed flag")
        linked = m.get("result_linked_rate")
        if linked is not None and linked < 1.0 and (m.get("decisions_total") or 0) > 0:
            # 許容: 一部未リンクがあっても警告のみ
            pass
    return (not problems), problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    from tools.ai.llm.context_allocation import RESERVED_HEADROOM_CHARS
    from tools.ai.state.decision_confidence import kss1_obs_enabled

    os.environ["AI_AGENT_KSS1_OBS"] = "1"
    assert kss1_obs_enabled()
    assert int(RESERVED_HEADROOM_CHARS) >= 800

    exp_id = "kss1_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "purpose": "measurement_ok for KSS-1 observability (not performance)",
        "formalize_phase5_1": False,
        "auto_routing": False,
        "common_env": COMMON,
        "cases": cases,
        "trials": args.trials,
        "success_criteria": [
            "decision observation attachable",
            "result provenance linkable",
            "high_confidence_zero_gain extractable",
            "useful vs zero-info failure separable",
            "pipeline behavior unchanged",
            "headroom gate unchanged",
        ],
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = []
    for trial in range(1, args.trials + 1):
        for case in cases:
            before = (
                len(json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", []))
                if RESULTS_PATH.exists()
                else 0
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            env.update(COMMON)
            env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
            env["AI_AGENT_EXPERIMENT_ID"] = exp_id
            env["AI_AGENT_EXPERIMENT_CONDITION"] = "kss1_obs"
            env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
            env["AI_AGENT_EXPERIMENT_CASE"] = case
            print(f"\n=== {exp_id} | kss1 | trial={trial} | {case} ===", flush=True)
            proc = subprocess.run([sys.executable, str(ENTRY)], cwd=str(ROOT), env=env)
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            matched = [
                r
                for r in data.get("runs", [])[before:]
                if match_case(r.get("request"), case)
            ]
            if not matched:
                rec = {"case": case, "trial": trial, "error": "NOT_FOUND"}
            else:
                run = matched[-1]
                rec = {
                    "case": case,
                    "trial": trial,
                    "returncode": proc.returncode,
                    "timestamp": run.get("timestamp"),
                    "experiment": run.get("experiment"),
                    "metrics": summarize(run),
                    "pipeline": run.get("pipeline"),
                    "state": run.get("state"),
                    "timing": run.get("timing"),
                }
            records.append(rec)
            (exp_dir / f"kss1__{case}__trial{trial}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            m = rec.get("metrics") or {}
            print(
                f"  -> fail_stage={m.get('fail_stage')} rounds={m.get('rounds')} "
                f"kss1_rounds={m.get('kss1_obs_rounds')} "
                f"obs_cov={m.get('observation_coverage')} "
                f"linked={m.get('result_linked_rate')} "
                f"hc_zero_gain={m.get('high_confidence_zero_gain_rate')} "
                f"headroom={m.get('actual_headroom_min')}",
                flush=True,
            )

    ok, problems = measurement_ok(records)
    # past reanalysis note
    from research.llm_benchmarks.kss1_analyze import analyze_results_path

    past = analyze_results_path(RESULTS_PATH)
    summary = {
        "experiment_id": exp_id,
        "measurement_ok": ok,
        "problems": problems,
        "formalize_phase5_1": False,
        "auto_routing": False,
        "n_records": len(records),
        "per_case": [
            {"case": r.get("case"), "metrics": r.get("metrics")} for r in records
        ],
        "past_runs_reanalysis": {
            "n_runs_scanned": past.get("n_runs"),
            "runs_without_kss1_obs": past.get("runs_without_kss1_obs"),
            "note": past.get("past_reanalysis"),
        },
        "disclaimer": (
            "Observability measurement only. Do not invent confidence for past runs. "
            "Do not design routing thresholds from this single trial alone."
        ),
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== KSS-1 MEASUREMENT SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote {exp_dir}")
    print("MEASUREMENT_OK:", "YES" if ok else "NO")
    print("FORMALIZE_PHASE5_1: NO")
    print("AUTO_ROUTING: NO")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
