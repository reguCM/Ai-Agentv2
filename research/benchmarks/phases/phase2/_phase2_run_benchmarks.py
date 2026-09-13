"""Phase 2 verification: run 5 benchmark cases once and print metrics."""
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
OUT_PATH = HERE / "_phase2_benchmark_summary.json"


def summarize(run, case):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    state = run.get("state") or {}
    prompt_state = {
        k: state.get(k)
        for k in (
            "task",
            "facts",
            "decisions",
            "selected_findings",
            "constraints",
            "open_questions",
            "unresolved",
        )
    }
    hist = pipe.get("research_history") or state.get("research_history") or []
    trace = run.get("trace") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    rounds_detail = pipe.get("research_rounds_detail") or []
    escalations = [
        (item.get("rule_partial") or {}).get("escalation")
        for item in rounds_detail
        if (item.get("rule_partial") or {}).get("escalation")
    ]
    return {
        "case": case,
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "usable": len(research.get("usable_findings") or []),
        "insufficient": len(research.get("insufficient_findings") or []),
        "stop_reason": research.get("stop_reason"),
        "context_overflow": overflow or run.get("error") == "context_overflow",
        "llm_calls": (run.get("timing") or {}).get("llm_calls"),
        "prompt_state_chars": len(json.dumps(prompt_state, ensure_ascii=False)),
        "history_events": len(hist),
        "open_questions": len(state.get("open_questions") or []),
        "banned_actions": len(state.get("banned_actions") or []),
        "selected_findings": len(state.get("selected_findings") or []),
        "escalation_reasons": escalations,
        "timing_total": (run.get("timing") or {}).get("total_seconds"),
    }


def match_case(request, case):
    mapping = {
        "memory_usage": "メモリ使用率",
        "cpu_temperature": "CPU温度",
        "disk_usage": "ディスク使用率",
        "gpu_usage": "GPUの使用率",
        "gpu_vram_usage": "GPU VRAM",
    }
    needle = mapping.get(case, case)
    return needle in (request or "")


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
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            env=env,
        )
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    summaries = []
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        if matched:
            summaries.append(summarize(matched[-1], case))
        else:
            summaries.append({"case": case, "error": "NOT_FOUND"})

    OUT_PATH.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== PHASE 2 SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
