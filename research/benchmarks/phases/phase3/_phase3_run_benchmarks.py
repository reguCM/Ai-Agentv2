"""Phase 3 shadow verification: 5 benchmark cases + Global Judge skip analysis."""
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
OUT_PATH = HERE / "_phase3_benchmark_summary.json"


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
    state = run.get("state") or {}
    shadow = pipe.get("global_judge_shadow") or {}
    trace = run.get("trace") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    timing = run.get("timing") or {}
    quality = shadow.get("quality") or {}
    return {
        "case": case,
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "context_overflow": overflow or run.get("error") == "context_overflow",
        "llm_calls": timing.get("llm_calls"),
        "llm_calls_actual_judge": shadow.get("judge_calls_actual"),
        "would_skip_count": shadow.get("would_skip_count"),
        "llm_calls_saved_estimate": shadow.get("llm_calls_saved_estimate"),
        "llm_calls_if_live_skip": (timing.get("llm_calls") or 0)
        - (shadow.get("llm_calls_saved_estimate") or 0),
        "critical_miss_count": quality.get("critical_miss_count"),
        "false_continue_count": quality.get("false_continue_count"),
        "satisfies_match_count": quality.get("satisfies_match_count"),
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
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    summaries = []
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        summaries.append(
            summarize(matched[-1], case) if matched else {"case": case, "error": "NOT_FOUND"}
        )

    OUT_PATH.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== PHASE 3 SHADOW SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
