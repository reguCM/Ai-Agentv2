"""Phase 5: Memory Recall gate on 5 baseline cases."""
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
OUT_PATH = HERE / "_phase5_benchmark_summary.json"
RESERVED_HEADROOM = 800


def match_case(request, case):
    mapping = {
        "memory_usage": "メモリ使用率",
        "cpu_temperature": "CPU温度",
        "disk_usage": "ディスク使用率",
        "gpu_usage": "GPUの使用率",
        "gpu_vram_usage": "GPU VRAM",
    }
    return mapping.get(case, case) in (request or "")


def _repeat_rate(run):
    """同一 command_key が候補として再提案された割合の粗い推定。"""
    details = (run.get("pipeline") or {}).get("research_rounds_detail") or []
    seen = set()
    repeats = 0
    total = 0
    for round_item in details:
        for cand in round_item.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            key = (str(cand.get("command") or ""), tuple(cand.get("args") or []))
            if not key[0]:
                continue
            total += 1
            if key in seen:
                repeats += 1
            seen.add(key)
    if total == 0:
        return None
    return round(repeats / total, 3)


def summarize(run, case):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    cb = pipe.get("context_budget_shadow") or {}
    cb_summary = cb.get("summary") or {}
    calls = cb.get("calls") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    research_reached = research.get("rounds") is not None

    modes = {}
    recalled_counts = []
    for item in calls:
        mode = item.get("recall_mode")
        if mode:
            modes[mode] = modes.get(mode, 0) + 1
        if item.get("recalled_event_count") is not None:
            recalled_counts.append(item.get("recalled_event_count"))

    headroom_violations = [
        item
        for item in calls
        if item.get("actual_headroom") is not None
        and int(item.get("actual_headroom")) < RESERVED_HEADROOM
    ]

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
        "research_reached": research_reached,
        "actual_headroom_min": cb_summary.get("actual_headroom_min"),
        "headroom_gate_ok": cb_summary.get("headroom_gate_ok"),
        "headroom_violation_count": len(headroom_violations),
        "allocated_chars_max": cb_summary.get("allocated_chars_max"),
        "recall_mode_counts": modes,
        "recalled_event_count_avg": (
            round(sum(recalled_counts) / len(recalled_counts), 2)
            if recalled_counts
            else None
        ),
        "recalled_event_count_max": max(recalled_counts) if recalled_counts else None,
        "repeat_same_command_rate": _repeat_rate(run),
        "reduction_applied_count": cb_summary.get("reduction_applied_count"),
        "defer_count": cb_summary.get("defer_count"),
    }


def main():
    before_count = 0
    if RESULTS_PATH.exists():
        before_count = len(
            json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
        )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["AI_AGENT_MEMORY_RECALL"] = "1"
    env["AI_AGENT_MEMORY_JUDGE"] = "0"
    env.setdefault("AI_AGENT_CONTEXT_ALLOC_LIVE", "1")
    env.setdefault("AI_AGENT_CONTEXT_ALLOC_SHADOW", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE", "3")
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== PHASE 5 MEMORY RECALL RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
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
    print("\n=== PHASE 5 BENCHMARK SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))

    problems = []
    for item in summaries:
        if item.get("error") == "NOT_FOUND":
            problems.append(f"{item['case']}: missing run")
            continue
        if item.get("context_overflow"):
            problems.append(f"{item['case']}: context_overflow")
        if item.get("research_reached") and not item.get("headroom_gate_ok"):
            problems.append(
                f"{item['case']}: headroom_gate FAIL min={item.get('actual_headroom_min')}"
            )
    print("\n=== GATE ===")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        print("PHASE5_OK: NO")
    else:
        print("OK: overflow none; headroom>=800; memory recall metrics recorded.")
        print("PHASE5_OK: YES")


if __name__ == "__main__":
    main()
