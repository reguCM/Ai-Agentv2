"""Phase 3.5 observation: live skip + AUDIT_RATE=3, compare vs baselines."""
import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent
import json
import os
import subprocess
import sys
from pathlib import Path

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
OUT_PATH = HERE / "_phase3_5_observation_summary.json"

# Step 2-2a POST / Phase 3 shadow baselines for extra_rounds
BASELINE_ROUNDS = {
    "memory_usage": 2,
    "cpu_temperature": 10,
    "disk_usage": 3,
    "gpu_usage": None,
    "gpu_vram_usage": 5,
}
# Phase 3 shadow: judge always called = rounds
SHADOW_JUDGE_CALLS = {
    "memory_usage": 3,
    "cpu_temperature": 10,
    "disk_usage": 10,
    "gpu_usage": 0,
    "gpu_vram_usage": 10,
}


def match_case(request, case):
    mapping = {
        "memory_usage": "メモリ使用率",
        "cpu_temperature": "CPU温度",
        "disk_usage": "ディスク使用率",
        "gpu_usage": "GPUの使用率",
        "gpu_vram_usage": "GPU VRAM",
    }
    return mapping.get(case, case) in (request or "")


def summarize(run, case):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    progress = pipe.get("progress") or []
    shadow = pipe.get("global_judge_shadow") or {}
    obs = shadow.get("observation") or {}
    quality = shadow.get("quality") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    rounds = research.get("rounds")
    baseline = BASELINE_ROUNDS.get(case)
    shadow_judges = SHADOW_JUDGE_CALLS.get(case)
    judge_actual = shadow.get("judge_calls_actual")
    live_skips = shadow.get("live_skip_count") or 0
    audit = shadow.get("audit_count") or 0

    extra_rounds = None
    if rounds is not None and baseline is not None:
        extra_rounds = int(rounds) - int(baseline)

    judge_saved_vs_shadow = None
    if shadow_judges is not None and judge_actual is not None:
        judge_saved_vs_shadow = int(shadow_judges) - int(judge_actual)

    # Research cost proxy: each extra round typically costs ~1 candidate LLM (+verify)
    research_extra_llm_est = extra_rounds if extra_rounds is not None else None
    net_llm_delta_est = None
    if judge_saved_vs_shadow is not None and research_extra_llm_est is not None:
        net_llm_delta_est = research_extra_llm_est - judge_saved_vs_shadow

    audit_rounds = [
        {
            "round": item.get("round"),
            "critical_miss": (item.get("quality_compare") or {}).get("critical_miss"),
            "decision_divergence": (item.get("quality_compare") or {}).get(
                "decision_divergence"
            ),
            "shadow_progress": (item.get("quality_compare") or {}).get(
                "shadow_progress_action"
            ),
            "actual_progress": (item.get("quality_compare") or {}).get(
                "actual_progress_action"
            ),
            "satisfies_match": (item.get("quality_compare") or {}).get(
                "satisfies_request_match"
            ),
        }
        for item in (shadow.get("rounds") or [])
        if item.get("audit_only") and item.get("quality_compare")
    ]

    last_progress = progress[-1] if progress else {}
    return {
        "case": case,
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "stop_reason": research.get("stop_reason"),
        "rounds": rounds,
        "baseline_rounds": baseline,
        "extra_rounds": extra_rounds,
        "last_progress_action": last_progress.get("action"),
        "last_progress_reason": last_progress.get("reason"),
        "context_overflow": overflow or run.get("error") == "context_overflow",
        "llm_calls": timing.get("llm_calls"),
        "judge_calls_actual": judge_actual,
        "shadow_judge_calls_baseline": shadow_judges,
        "judge_saved_vs_shadow": judge_saved_vs_shadow,
        "live_skip_count": live_skips,
        "audit_count": audit,
        "llm_calls_saved_actual": shadow.get("llm_calls_saved_actual"),
        "judge_reduction_rate": obs.get("judge_reduction_rate"),
        "critical_miss_count": quality.get("critical_miss_count"),
        "decision_divergence_count": quality.get("decision_divergence_count"),
        "audit_compared_count": quality.get("audit_compared_count"),
        "research_extra_llm_est": research_extra_llm_est,
        "net_llm_delta_est": net_llm_delta_est,
        "audit_rounds": audit_rounds,
        "timing_total": timing.get("total_seconds"),
    }


def main():
    before_count = 0
    if RESULTS_PATH.exists():
        before_count = len(
            json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
        )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP"] = "1"
    env["AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE"] = "3"
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== PHASE 3.5 AUDIT_RATE=3 RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    summaries = []
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        if matched:
            item = summarize(matched[-1], case)
            # attach baseline_rounds into observation for persistence clarity
            shadow = (matched[-1].get("pipeline") or {}).get("global_judge_shadow") or {}
            if shadow.get("observation") is not None:
                item["observation"] = shadow.get("observation")
            summaries.append(item)
        else:
            summaries.append({"case": case, "error": "NOT_FOUND"})

    OUT_PATH.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== PHASE 3.5 OBSERVATION SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))

    # Gate criteria
    problems = []
    for item in summaries:
        if item.get("error") == "NOT_FOUND":
            problems.append(f"{item['case']}: missing run")
            continue
        if item.get("context_overflow"):
            problems.append(f"{item['case']}: context_overflow")
        if (item.get("critical_miss_count") or 0) > 0:
            problems.append(
                f"{item['case']}: critical_miss={item.get('critical_miss_count')}"
            )
        if (item.get("decision_divergence_count") or 0) > 0:
            problems.append(
                f"{item['case']}: decision_divergence={item.get('decision_divergence_count')}"
            )
        if item.get("case") == "cpu_temperature" and item.get("rounds") is not None:
            if int(item["rounds"]) < 10 and item.get("error") not in (
                "stagnation",
                "findings_complete",
                None,
            ):
                pass  # non-deterministic; only flag overflow/critical
    print("\n=== GATE ===")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
    else:
        print("OK: no critical_miss / decision_divergence / overflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
