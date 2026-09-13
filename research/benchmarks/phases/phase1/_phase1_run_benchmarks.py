"""Phase 1 verification: run 5 benchmark cases once and print metrics."""
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


def summarize(run):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    state = run.get("state") or {}
    prompt_state = {k: state.get(k) for k in (
        "task", "facts", "decisions", "selected_findings",
        "constraints", "open_questions", "unresolved",
    )}
    hist = pipe.get("research_history") or state.get("research_history") or []
    trace = run.get("trace") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    return {
        "case": run.get("_case"),
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "usable": len(research.get("usable_findings") or []),
        "insufficient": len(research.get("insufficient_findings") or []),
        "stop_reason": research.get("stop_reason"),
        "context_overflow": overflow or run.get("error") == "context_overflow",
        "prompt_state_chars": len(json.dumps(prompt_state, ensure_ascii=False)),
        "persistence_state_chars": len(json.dumps(state, ensure_ascii=False)),
        "history_events": len(hist),
        "open_questions": len(state.get("open_questions") or []),
        "unresolved": len(state.get("unresolved") or []),
        "timing_total": (run.get("timing") or {}).get("total_seconds"),
    }


def main():
    before_count = 0
    if RESULTS_PATH.exists():
        before_count = len(json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", []))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"
    summaries = []

    for case in CASES:
        if case == "cpu_temperature":
            continue  # already run in this session
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== RUN {case} ===", flush=True)
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            env=env,
            capture_output=False,
        )
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    case_runs = {}
    for run in new_runs:
        req = run.get("request") or ""
        for case in CASES:
            if case.replace("_", " ") in req.lower() or case.split("_")[0] in req.lower():
                case_runs[case] = run
                break

    # include cpu_temperature latest from full runs
    for run in reversed(data.get("runs", [])):
        req = run.get("request") or ""
        if "cpu温度" in req and "cpu_temperature" not in case_runs:
            run = dict(run)
            run["_case"] = "cpu_temperature"
            summaries.append(summarize(run))

    for case, run in case_runs.items():
        run = dict(run)
        run["_case"] = case
        summaries.append(summarize(run))

    out_path = HERE / "_phase1_benchmark_summary.json"
    out_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== PHASE 1 SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
