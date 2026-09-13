"""
Knowledge Source Selection 観測ベンチ（行動変更なし）。

Phase 4 live と同一の実行経路に観測だけを載せる。
P4/P5/P5.1 制御比較の結果は改変せず参考基線のまま。

Usage:
  py -3.14 _knowledge_source_observe_bench.py
  py -3.14 _knowledge_source_observe_bench.py --cases memory_usage,cpu_temperature
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
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "knowledge_source_obs"
ENTRY = ROOT / "research" / "llm_benchmarks" / "research_implement.py"
BASELINE_NOTE = ROOT / "research" / "llm_benchmarks" / "baselines" / "phase4_phase5_reference"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
CASE_SNIPPET = {
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
    # Phase 4 live と同一行動。観測のみ追加。
    "AI_AGENT_MEMORY_RECALL": "0",
    "AI_AGENT_MEMORY_RECALL_VERSION": "none",
    "AI_AGENT_KNOWLEDGE_SOURCE_OBS": "1",
}


def match_case(request, case):
    return CASE_SNIPPET.get(case, case) in (request or "")


def summarize_kss(run):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    cb = pipe.get("context_budget_shadow") or {}
    rounds = pipe.get("research_rounds_detail") or []
    hist = pipe.get("research_history") or []
    obs_rounds = []
    preferred = []
    coverage_vals = []
    calibrated = 0
    linked = 0
    for item in rounds:
        obs = item.get("knowledge_source_observation") or {}
        if not obs.get("enabled"):
            continue
        obs_rounds.append(obs)
        sel = obs.get("knowledge_source_selection") or {}
        if sel.get("preferred_source"):
            preferred.append(sel["preferred_source"])
        cov = obs.get("known_coverage") or {}
        if cov.get("known_coverage") is not None:
            coverage_vals.append(cov["known_coverage"])
        for p in (obs.get("calibration") or {}).get("proposals") or []:
            calibrated += 1
            if p.get("result_linked"):
                linked += 1
    kss_hist = [e for e in hist if e.get("type") == "knowledge_source_obs"]
    overflow = any(
        (t.get("error") == "context_overflow") for t in (run.get("trace") or [])
    ) or run.get("error") == "context_overflow"
    return {
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "llm_calls": timing.get("llm_calls"),
        "usable_findings": len(research.get("usable_findings") or []),
        "actual_headroom_min": (cb.get("summary") or {}).get("actual_headroom_min"),
        "headroom_gate_ok": (cb.get("summary") or {}).get("headroom_gate_ok"),
        "context_overflow": overflow,
        "kss_obs_rounds": len(obs_rounds),
        "kss_history_events": len(kss_hist),
        "preferred_sources": preferred,
        "known_coverage_mean": (
            round(sum(coverage_vals) / len(coverage_vals), 3) if coverage_vals else None
        ),
        "proposals_calibrated": calibrated,
        "proposals_result_linked": linked,
        "auto_switch": False,
        "behavior_changed": False,
        "note": "observation_only_same_path_as_phase4_live",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    # preflight: obs module + headroom constant
    from tools.ai.llm.context_allocation import RESERVED_HEADROOM_CHARS
    from tools.ai.state.knowledge_source import knowledge_source_obs_enabled

    os.environ["AI_AGENT_KNOWLEDGE_SOURCE_OBS"] = "1"
    assert knowledge_source_obs_enabled()
    assert int(RESERVED_HEADROOM_CHARS) >= 800

    exp_id = "kss_obs_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "formalize_phase5_1": False,
        "auto_switch": False,
        "behavior": "phase4_live_plus_observation",
        "common_env": COMMON,
        "cases": cases,
        "trials": args.trials,
        "reference_baselines": str(BASELINE_NOTE),
        "success_criteria": (
            "Measure provenance / value estimates / calibration links; "
            "do not require success-rate improvement."
        ),
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = []
    for trial in range(1, args.trials + 1):
        for case in cases:
            before = 0
            if RESULTS_PATH.exists():
                before = len(
                    json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
                )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            env.update(COMMON)
            env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
            env["AI_AGENT_EXPERIMENT_ID"] = exp_id
            env["AI_AGENT_EXPERIMENT_CONDITION"] = "kss_obs"
            env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
            env["AI_AGENT_EXPERIMENT_CASE"] = case
            print(f"\n=== {exp_id} | kss_obs | trial={trial} | {case} ===", flush=True)
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
                    "metrics": summarize_kss(run),
                    # History / rounds 完全保存
                    "pipeline": run.get("pipeline"),
                    "state": run.get("state"),
                    "timing": run.get("timing"),
                }
            records.append(rec)
            (exp_dir / f"kss_obs__{case}__trial{trial}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            m = rec.get("metrics") or {}
            print(
                f"  -> fail_stage={m.get('fail_stage')} rounds={m.get('rounds')} "
                f"kss_rounds={m.get('kss_obs_rounds')} "
                f"preferred={m.get('preferred_sources')} "
                f"linked={m.get('proposals_result_linked')}/{m.get('proposals_calibrated')} "
                f"headroom={m.get('actual_headroom_min')}",
                flush=True,
            )

    summary = {
        "experiment_id": exp_id,
        "formalize_phase5_1": False,
        "n_records": len(records),
        "per_case": [
            {"case": r.get("case"), "trial": r.get("trial"), "metrics": r.get("metrics")}
            for r in records
        ],
        "measurement_ok": all(
            (r.get("metrics") or {}).get("kss_obs_rounds", 0) > 0
            or (r.get("metrics") or {}).get("rounds") is None
            for r in records
            if r.get("error") != "NOT_FOUND"
        ),
        "disclaimer": (
            "Observation-only. Do not compare causally to past P4/P5/P5.1 trials. "
            "No Decision thresholds applied."
        ),
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== KSS OBS SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nWrote {exp_dir}")
    print("FORMALIZE_PHASE5_1: NO")
    print("AUTO_SWITCH: NO")


if __name__ == "__main__":
    main()
