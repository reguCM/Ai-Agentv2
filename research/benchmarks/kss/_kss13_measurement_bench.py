"""
KSS-1.3 measurement bench（探索価値・情報利得の観測）。

行動経路は変更しない。観測のみ。
--offline-from で既存実験 JSON から再構築可能（無い値は missing）。
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

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
REQUIRED = ["memory_usage", "cpu_temperature", "disk_usage", "gpu_vram_usage"]
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
    "AI_AGENT_KSS1_OBS": "0",
    "AI_AGENT_KSS11_OBS": "1",
    "AI_AGENT_KSS12_OBS": "1",
    "AI_AGENT_KSS13_OBS": "1",
}


def match_case(request, case):
    return SNIPPET.get(case, case) in (request or "")


def summarize(run):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    cb = (pipe.get("context_budget_shadow") or {}).get("summary") or {}
    rounds = pipe.get("research_rounds_detail") or []
    kss13 = [
        item.get("exploration_value_observation")
        for item in rounds
        if isinstance(item.get("exploration_value_observation"), dict)
        and item["exploration_value_observation"].get("enabled")
    ]
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
        "kss13_obs_rounds": len(kss13),
        "behavior_changed": False,
        "stop_reason": research.get("stop_reason"),
    }


def run_offline(src_dir: Path, exp_dir: Path, cases):
    """既存 round_details から観測を再構築して case JSON を書く。"""
    from tools.ai.state.exploration_value import rebuild_from_round_details

    src_dir = Path(src_dir)
    written = []
    for path in sorted(src_dir.glob("*.json")):
        if path.name in ("summary.json", "manifest.json"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        case = rec.get("case")
        if cases and case not in cases:
            # try parse from filename kss11__case__trial1
            for c in cases:
                if f"__{c}__" in path.name:
                    case = c
                    rec["case"] = c
                    break
            else:
                continue
        pipe = rec.get("pipeline") or {}
        metrics = rec.get("metrics") or {}
        bundles = rebuild_from_round_details(
            pipe.get("research_rounds_detail") or [],
            progress_log=pipe.get("progress") or [],
            case_id=case,
            research_run_id=exp_dir.name,
            final_pass=metrics.get("pass", rec.get("pass")),
            fail_stage=metrics.get("fail_stage", rec.get("fail_stage")),
            fail_reason=rec.get("error")
            or (pipe.get("research") or {}).get("stop_reason"),
        )
        # attach into pipeline for analyzer
        by_round = {b.get("round_index"): b for b in bundles}
        for item in pipe.get("research_rounds_detail") or []:
            obs = by_round.get(item.get("round"))
            if obs:
                item["exploration_value_observation"] = obs
        pipe["exploration_value_rounds"] = bundles
        rec["pipeline"] = pipe
        rec["case"] = case
        rec["kss13_mode"] = "offline_rebuild"
        out = exp_dir / f"kss13__{case}__trial1.json"
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(case)
        print(f"  offline rebuild: {case} rounds={len(bundles)}", flush=True)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(REQUIRED))
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument(
        "--offline-from",
        default="",
        help="既存実験 dir から再構築（LLM 再実行なし）",
    )
    parser.add_argument("--live", action="store_true", help="LLM ライブ実行")
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    from tools.ai.llm.context_allocation import RESERVED_HEADROOM_CHARS
    from tools.ai.state.exploration_value import kss13_obs_enabled

    assert int(RESERVED_HEADROOM_CHARS) >= 800

    exp_id = "kss13_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "purpose": "KSS-1.3 exploration value / information gain observation",
        "formalize_phase5_1": False,
        "auto_routing": False,
        "confidence_threshold": False,
        "web_force": False,
        "common_env": COMMON,
        "cases": cases,
        "trials": args.trials,
        "mode": "live" if args.live else "offline_rebuild",
        "offline_from": args.offline_from or None,
        "available_fields": [
            "kept_hit_count",
            "candidate_count",
            "new_url/source/term counts",
            "link_coverage",
            "information_gain_existing",
            "no_gain_existing",
            "token/url jaccard",
        ],
        "missing_fields": [
            "search_result_count (unless web_exec live)",
            "new_entity_count",
            "exploration_value_score",
            "semantic_novelty",
        ],
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.live:
        src = Path(args.offline_from) if args.offline_from else (
            ROOT
            / "research"
            / "llm_benchmarks"
            / "kss11_measurement"
            / "kss11_20260820_151041"
        )
        print(f"=== {exp_id} offline from {src} ===", flush=True)
        run_offline(src, exp_dir, cases)
    else:
        os.environ["AI_AGENT_KSS13_OBS"] = "1"
        os.environ["AI_AGENT_KSS11_OBS"] = "1"
        os.environ["AI_AGENT_KSS12_OBS"] = "1"
        assert kss13_obs_enabled()
        for trial in range(1, args.trials + 1):
            for case in cases:
                before = (
                    len(
                        json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get(
                            "runs", []
                        )
                    )
                    if RESULTS_PATH.exists()
                    else 0
                )
                env = os.environ.copy()
                env["PYTHONPATH"] = str(ROOT)
                env.update(COMMON)
                env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
                env["AI_AGENT_EXPERIMENT_ID"] = exp_id
                env["AI_AGENT_EXPERIMENT_CONDITION"] = "kss13_obs"
                env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
                env["AI_AGENT_EXPERIMENT_CASE"] = case
                print(f"\n=== {exp_id} | live | trial={trial} | {case} ===", flush=True)
                proc = subprocess.run(
                    [sys.executable, str(ENTRY)], cwd=str(ROOT), env=env
                )
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
                        "timing": run.get("timing"),
                        "kss13_mode": "live",
                    }
                (exp_dir / f"kss13__{case}__trial{trial}.json").write_text(
                    json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                m = rec.get("metrics") or {}
                print(
                    f"  -> pass={m.get('pass')} fail_stage={m.get('fail_stage')} "
                    f"rounds={m.get('rounds')} kss13={m.get('kss13_obs_rounds')} "
                    f"headroom={m.get('actual_headroom_min')}",
                    flush=True,
                )

    # analyze
    from research.llm_benchmarks.kss13_analyze import analyze_experiment_dir, write_report

    summary = analyze_experiment_dir(exp_dir)
    summary["experiment_id"] = exp_id
    summary["manifest"] = manifest
    summary["behavior_unchanged"] = True
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(summary, exp_dir / "report.md")
    print(f"\nWrote {exp_dir / 'summary.json'}")
    print(f"Wrote {exp_dir / 'report.md'}")
    print("MEASUREMENT_OK: YES (observation rebuild/live; no routing)")


if __name__ == "__main__":
    main()
