"""Phase 4: context allocation shadow measurement on 5 baseline cases."""
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
P35_PATH = HERE.parent / "phase3" / "_phase3_5_observation_summary.json"
OUT_PATH = HERE / "_phase4_benchmark_summary.json"


def match_case(request, case):
    mapping = {
        "memory_usage": "メモリ使用率",
        "cpu_temperature": "CPU温度",
        "disk_usage": "ディスク使用率",
        "gpu_usage": "GPUの使用率",
        "gpu_vram_usage": "GPU VRAM",
    }
    return mapping.get(case, case) in (request or "")


def load_p35_baseline(case):
    if not P35_PATH.exists():
        return {}
    for item in json.loads(P35_PATH.read_text(encoding="utf-8")):
        if item.get("case") == case:
            return item
    return {}


def summarize(run, case, p35):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    cb = pipe.get("context_budget_shadow") or {}
    cb_summary = cb.get("summary") or {}
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    calls = cb.get("calls") or []

    return {
        "case": case,
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "stop_reason": research.get("stop_reason"),
        "rounds": research.get("rounds"),
        "context_overflow": overflow or run.get("error") == "context_overflow",
        "llm_calls": timing.get("llm_calls"),
        "usable_findings": len((research.get("usable_findings") or [])),
        "insufficient_findings": len((research.get("insufficient_findings") or [])),
        "result": run.get("pass"),
        "context_budget_mode": cb.get("mode"),
        "legacy_chars_total": cb_summary.get("legacy_chars_total"),
        "allocated_chars_total": cb_summary.get("allocated_chars_total"),
        "legacy_chars_max": cb_summary.get("legacy_chars_max"),
        "allocated_chars_max": cb_summary.get("allocated_chars_max"),
        "allocated_headroom_min": cb_summary.get("allocated_headroom_min"),
        "legacy_overflow_count": cb_summary.get("legacy_overflow_count"),
        "allocated_overflow_count": cb_summary.get("allocated_overflow_count"),
        "reduction_applied_count": cb_summary.get("reduction_applied_count"),
        "defer_count": cb_summary.get("defer_count"),
        "p35_baseline": {
            "rounds": p35.get("rounds"),
            "llm_calls": p35.get("llm_calls"),
            "legacy_overflow": p35.get("context_overflow"),
            "legacy_chars_max_est": p35.get("legacy_chars_max"),
        },
        "sample_calls": calls[:3],
    }


def main():
    before_count = 0
    if RESULTS_PATH.exists():
        before_count = len(
            json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
        )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["AI_AGENT_CONTEXT_ALLOC_SHADOW"] = "1"
    env["AI_AGENT_CONTEXT_ALLOC_LIVE"] = "0"
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE", "3")
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== PHASE 4 SHADOW RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    summaries = []
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        p35 = load_p35_baseline(case)
        if matched:
            summaries.append(summarize(matched[-1], case, p35))
        else:
            summaries.append({"case": case, "error": "NOT_FOUND"})

    OUT_PATH.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== PHASE 4 BENCHMARK SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))

    problems = []
    for item in summaries:
        if item.get("error") == "NOT_FOUND":
            problems.append(f"{item['case']}: missing run")
            continue
        if item.get("context_overflow"):
            problems.append(f"{item['case']}: context_overflow")
        if item.get("pass") is False and item.get("fail_stage") not in (
            None,
            "research",
            "judge",
            "implementation",
        ):
            problems.append(f"{item['case']}: unexpected fail_stage={item.get('fail_stage')}")
    print("\n=== GATE ===")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
    else:
        print("OK: no overflow; shadow metrics recorded.")


if __name__ == "__main__":
    main()
