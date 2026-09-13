"""
Phase 4 live vs Phase 5 Memory Recall 比較ベンチ。

正式化前ゲート:
  Memory Recall が無意味な同一 command_key 反復を減らしたか
  headroom / overflow を悪化させていないか
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
OUT_PATH = HERE / "_phase5_vs_phase4_compare.json"
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


def _command_key(command, args):
    return (str(command or "").strip(), tuple(str(a) for a in (args or [])))


def metrics_from_history(events):
    fails = [
        e
        for e in (events or [])
        if e.get("type") == "verify_fail"
        or (isinstance(e.get("result"), dict) and e.get("result", {}).get("ok") is False)
    ]
    seen = set()
    repeats = 0
    keys = []
    for event in fails:
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        key = _command_key((action or {}).get("command"), (action or {}).get("args"))
        if not key[0]:
            continue
        keys.append(key)
        if key in seen:
            repeats += 1
        seen.add(key)
    # max streak by command_key (chronological)
    max_streak = 0
    streak = 0
    prev = None
    for key in keys:
        if key == prev:
            streak += 1
        else:
            streak = 1
            prev = key
        max_streak = max(max_streak, streak)
    total = len(keys)
    return {
        "verify_fail_count": total,
        "unique_command_keys": len(seen),
        "repeat_fail_count": repeats,
        "repeat_fail_rate": round(repeats / total, 3) if total else None,
        "max_command_streak": max_streak if total else 0,
    }


def metrics_from_rounds(round_details):
    """候補・検証結果から command_key 再提案率。"""
    seen_cand = set()
    cand_total = 0
    cand_repeats = 0
    seen_fail = set()
    fail_total = 0
    fail_repeats = 0
    for item in round_details or []:
        for cand in item.get("candidate_keys") or []:
            key = _command_key(cand.get("command"), cand.get("args"))
            if not key[0]:
                continue
            cand_total += 1
            if key in seen_cand:
                cand_repeats += 1
            seen_cand.add(key)
        for run in item.get("verified_runs") or []:
            if run.get("ok"):
                continue
            key = _command_key(run.get("command"), run.get("args"))
            if not key[0]:
                continue
            fail_total += 1
            if key in seen_fail:
                fail_repeats += 1
            seen_fail.add(key)
    return {
        "candidate_total": cand_total,
        "candidate_repeat_rate": (
            round(cand_repeats / cand_total, 3) if cand_total else None
        ),
        "verified_fail_total": fail_total,
        "verified_fail_repeat_rate": (
            round(fail_repeats / fail_total, 3) if fail_total else None
        ),
    }


def summarize_run(run, case, label):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    trace = run.get("trace") or []
    cb = pipe.get("context_budget_shadow") or {}
    cb_summary = cb.get("summary") or {}
    calls = cb.get("calls") or []
    overflow = any(t.get("error") == "context_overflow" for t in trace)
    hist = pipe.get("research_history") or []
    rounds_detail = pipe.get("research_rounds_detail") or []
    hist_m = metrics_from_history(hist)
    round_m = metrics_from_rounds(rounds_detail)
    modes = {}
    for item in calls:
        mode = item.get("recall_mode")
        if mode:
            modes[mode] = modes.get(mode, 0) + 1
    return {
        "label": label,
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
        "actual_headroom_min": cb_summary.get("actual_headroom_min"),
        "headroom_gate_ok": cb_summary.get("headroom_gate_ok"),
        "allocated_chars_max": cb_summary.get("allocated_chars_max"),
        "recall_mode_counts": modes,
        **hist_m,
        **round_m,
    }


def run_suite(label, env_extra):
    before = 0
    if RESULTS_PATH.exists():
        before = len(
            json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", [])
        )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("AI_AGENT_CONTEXT_ALLOC_LIVE", "1")
    env.setdefault("AI_AGENT_CONTEXT_ALLOC_SHADOW", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP", "1")
    env.setdefault("AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE", "3")
    env["AI_AGENT_MEMORY_JUDGE"] = "0"
    env.update(env_extra)
    script = ROOT / "research" / "llm_benchmarks" / "research_implement.py"
    for case in CASES:
        env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
        print(f"\n=== {label} RUN {case} ===", flush=True)
        proc = subprocess.run([sys.executable, str(script)], cwd=str(ROOT), env=env)
        if proc.returncode not in (0, 1):
            print(f"ERROR: {case} exited {proc.returncode}", flush=True)
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before:]
    by_case = {}
    for case in CASES:
        matched = [r for r in new_runs if match_case(r.get("request"), case)]
        if matched:
            by_case[case] = summarize_run(matched[-1], case, label)
        else:
            by_case[case] = {"case": case, "label": label, "error": "NOT_FOUND"}
    return by_case


def compare_case(p4, p5):
    def delta(key):
        a, b = p4.get(key), p5.get(key)
        if a is None or b is None:
            return None
        try:
            return round(float(b) - float(a), 3)
        except (TypeError, ValueError):
            return None

    return {
        "case": p4.get("case") or p5.get("case"),
        "phase4": p4,
        "phase5": p5,
        "delta": {
            "rounds": delta("rounds"),
            "llm_calls": delta("llm_calls"),
            "usable_findings": delta("usable_findings"),
            "actual_headroom_min": delta("actual_headroom_min"),
            "verify_fail_count": delta("verify_fail_count"),
            "repeat_fail_rate": delta("repeat_fail_rate"),
            "max_command_streak": delta("max_command_streak"),
            "candidate_repeat_rate": delta("candidate_repeat_rate"),
            "verified_fail_repeat_rate": delta("verified_fail_repeat_rate"),
        },
        "repeat_improved": _repeat_improved(p4, p5),
        "headroom_ok": bool(p5.get("headroom_gate_ok") or not p5.get("research_reached", True))
        if p5.get("rounds") is not None
        else (not p5.get("context_overflow")),
        "overflow_ok": not p5.get("context_overflow") and not p4.get("context_overflow"),
    }


def _repeat_improved(p4, p5):
    """反復率が下がった / 同等なら True。Research 未到達は N/A。"""
    if p4.get("rounds") is None or p5.get("rounds") is None:
        return None
    r4 = p4.get("repeat_fail_rate")
    r5 = p5.get("repeat_fail_rate")
    if r4 is None or r5 is None:
        # fallback: streak
        s4, s5 = p4.get("max_command_streak"), p5.get("max_command_streak")
        if s4 is None or s5 is None:
            return None
        return s5 <= s4
    return r5 <= r4


def main():
    print("=== PHASE 4 LIVE (MEMORY_RECALL=0) ===", flush=True)
    p4 = run_suite(
        "phase4_live",
        {"AI_AGENT_MEMORY_RECALL": "0"},
    )
    print("\n=== PHASE 5 RECALL (MEMORY_RECALL=1) ===", flush=True)
    p5 = run_suite(
        "phase5_recall",
        {"AI_AGENT_MEMORY_RECALL": "1"},
    )

    comparisons = []
    for case in CASES:
        comparisons.append(compare_case(p4.get(case) or {}, p5.get(case) or {}))

    payload = {
        "phase4_live": p4,
        "phase5_recall": p5,
        "comparisons": comparisons,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== COMPARISON TABLE ===")
    for item in comparisons:
        d = item.get("delta") or {}
        print(
            f"{item['case']}: "
            f"repeat_fail_rate Δ={d.get('repeat_fail_rate')} "
            f"streak Δ={d.get('max_command_streak')} "
            f"rounds Δ={d.get('rounds')} "
            f"headroom_min Δ={d.get('actual_headroom_min')} "
            f"repeat_improved={item.get('repeat_improved')}"
        )

    problems = []
    improved = 0
    comparable = 0
    for item in comparisons:
        case = item["case"]
        p5 = item.get("phase5") or {}
        if p5.get("error") == "NOT_FOUND":
            problems.append(f"{case}: missing phase5 run")
            continue
        if p5.get("context_overflow"):
            problems.append(f"{case}: phase5 context_overflow")
        if p5.get("rounds") is not None and not p5.get("headroom_gate_ok"):
            problems.append(
                f"{case}: phase5 headroom_gate FAIL min={p5.get('actual_headroom_min')}"
            )
        if item.get("repeat_improved") is not None:
            comparable += 1
            if item.get("repeat_improved"):
                improved += 1
            else:
                problems.append(
                    f"{case}: repeat_fail_rate worsened "
                    f"(p4={item['phase4'].get('repeat_fail_rate')} "
                    f"p5={item['phase5'].get('repeat_fail_rate')})"
                )

    print("\n=== GATE (Phase5 formalize) ===")
    print(f"repeat_improved: {improved}/{comparable} research-reached cases")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(" -", p)
        # Formalize only if no overflow/headroom regression; repeat worsening is soft warn
        hard = [p for p in problems if "overflow" in p or "headroom" in p or "missing" in p]
        if hard:
            print("FORMALIZE_READY: NO")
        else:
            print("FORMALIZE_READY: CAUTION (repeat regression on some cases; review deltas)")
    else:
        print("OK: headroom/overflow stable; repeat rates not worsened.")
        print("FORMALIZE_READY: YES")

    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
