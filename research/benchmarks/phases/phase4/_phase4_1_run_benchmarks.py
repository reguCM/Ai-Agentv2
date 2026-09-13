"""Phase 4.1: context allocation benchmarks (shadow / live).

Phase 4 正式化後の通常経路は live（allocated 送信）。
  py -3.14 research/benchmarks/phases/phase4/_phase4_1_run_benchmarks.py --live   # live 確認
  py -3.14 research/benchmarks/phases/phase4/_phase4_1_run_benchmarks.py          # legacy 送信の shadow 比較
"""
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
P4_PATH = HERE / "_phase4_benchmark_summary.json"
OUT_PATH = HERE / "_phase4_1_benchmark_summary.json"
OUT_PATH_LIVE = HERE / "_phase4_1_live_summary.json"
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


def load_p4_baseline(case):
    if not P4_PATH.exists():
        return {}
    for item in json.loads(P4_PATH.read_text(encoding="utf-8")):
        if item.get("case") == case:
            return item
    return {}


def summarize(run, case, p4):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    cb = pipe.get("context_budget_shadow") or {}
    cb_summary = cb.get("summary") or {}
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    calls = cb.get("calls") or []
    research_reached = research.get("rounds") is not None

    headroom_violations = [
        {
            "builder": item.get("builder"),
            "allocated_chars": item.get("allocated_chars"),
            "actual_headroom": item.get("actual_headroom"),
            "reduction_label": item.get("reduction_label"),
            "omitted_categories": item.get("omitted_categories"),
        }
        for item in calls
        if (item.get("actual_headroom") is None)
        or int(item.get("actual_headroom")) < RESERVED_HEADROOM
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
        "context_budget_mode": cb.get("mode"),
        "legacy_chars_total": cb_summary.get("legacy_chars_total"),
        "allocated_chars_total": cb_summary.get("allocated_chars_total"),
        "legacy_chars_max": cb_summary.get("legacy_chars_max"),
        "allocated_chars_max": cb_summary.get("allocated_chars_max"),
        "reserved_headroom": cb_summary.get("reserved_headroom", RESERVED_HEADROOM),
        "actual_headroom_min": cb_summary.get("actual_headroom_min"),
        "actual_headroom_max": cb_summary.get("actual_headroom_max"),
        "headroom_gate_ok": cb_summary.get("headroom_gate_ok"),
        "headroom_violation_count": cb_summary.get("headroom_violation_count"),
        "legacy_overflow_count": cb_summary.get("legacy_overflow_count"),
        "allocated_overflow_count": cb_summary.get("allocated_overflow_count"),
        "reduction_applied_count": cb_summary.get("reduction_applied_count"),
        "defer_count": cb_summary.get("defer_count"),
        "headroom_violations": headroom_violations[:5],
        "p4_shadow_baseline": {
            "rounds": p4.get("rounds"),
            "llm_calls": p4.get("llm_calls"),
            "allocated_headroom_min_old": p4.get("allocated_headroom_min"),
            "allocated_chars_max": p4.get("allocated_chars_max"),
            "context_overflow": p4.get("context_overflow"),
        },
        "sample_calls": [
            {
                "builder": c.get("builder"),
                "legacy_chars": c.get("legacy_chars"),
                "allocated_chars": c.get("allocated_chars"),
                "actual_headroom": c.get("actual_headroom"),
                "reserved_headroom": c.get("reserved_headroom"),
                "effective_budget": c.get("effective_budget"),
                "reduction_label": c.get("reduction_label"),
                "omitted_categories": c.get("omitted_categories"),
                "retrieve_count": c.get("retrieve_count"),
                "usable_findings_count": c.get("usable_findings_count"),
                "open_questions_count": c.get("open_questions_count"),
                "allocated_sections": c.get("allocated_sections"),
            }
            for c in calls[:3]
        ],
    }


def main():
    live = "--live" in sys.argv or os.environ.get(
        "AI_AGENT_CONTEXT_ALLOC_LIVE", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    out_path = OUT_PATH_LIVE if live else OUT_PATH
    mode_label = "LIVE" if live else "SHADOW"

    before_count = 0
    if RESULTS_PATH.exists():
        before_count = len(
            json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
        )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["AI_AGENT_CONTEXT_ALLOC_SHADOW"] = "1"
    env["AI_AGENT_CONTEXT_ALLOC_LIVE"] = "1" if live else "0"
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE", "3")
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== PHASE 4.1 {mode_label} RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before_count:]
    summaries = []
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        p4 = load_p4_baseline(case)
        if matched:
            item = summarize(matched[-1], case, p4)
            item["run_mode"] = "live" if live else "shadow"
            summaries.append(item)
        else:
            summaries.append({"case": case, "error": "NOT_FOUND", "run_mode": mode_label.lower()})

    out_path.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n=== PHASE 4.1 {mode_label} BENCHMARK SUMMARY ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))

    problems = []
    live_ready = True
    for item in summaries:
        if item.get("error") == "NOT_FOUND":
            problems.append(f"{item['case']}: missing run")
            live_ready = False
            continue
        if item.get("context_overflow"):
            problems.append(f"{item['case']}: context_overflow")
            live_ready = False
        if item.get("research_reached") and not item.get("headroom_gate_ok"):
            problems.append(
                f"{item['case']}: headroom_gate FAIL "
                f"(min={item.get('actual_headroom_min')}, "
                f"violations={item.get('headroom_violation_count')})"
            )
            live_ready = False
        if item.get("research_reached") and (
            item.get("allocated_overflow_count") or 0
        ) > 0:
            problems.append(
                f"{item['case']}: allocated_overflow_count="
                f"{item.get('allocated_overflow_count')}"
            )
            live_ready = False
        if live and (item.get("defer_count") or 0) > 0:
            problems.append(f"{item['case']}: defer_count={item.get('defer_count')}")

    print(f"\n=== GATE (headroom >= 800) [{mode_label}] ===")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        print("LIVE_OK: NO" if live else "LIVE_READY: NO")
    else:
        print("OK: overflow none; actual_headroom >= 800 on all research-reached calls.")
        if live:
            print("LIVE_OK: YES")
        else:
            print("LIVE_READY: YES" if live_ready else "LIVE_READY: NO")


if __name__ == "__main__":
    main()
