"""Phase 4/5/5.1 同一条件再現可能性の調査（LLM 実行なし）。"""
from __future__ import annotations

import sys
from pathlib import Path

_BENCH = next(p for p in Path(__file__).resolve().parents if (p / "common_paths.py").is_file())
if str(_BENCH) not in sys.path:
    sys.path.insert(0, str(_BENCH))
from common_paths import REPO_ROOT

ROOT = REPO_ROOT
HERE = Path(__file__).resolve().parent
import json
from datetime import datetime
from pathlib import Path

RESULTS = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
COMPARE = HERE / "_phase5_vs_phase4_compare.json"
SUMMARY = HERE / "_phase5_benchmark_summary.json"
ANALYSIS = HERE / "_phase5_1_repetition_analysis.json"
V5_RESTORE = HERE / "_phase5_memory_recall_v5_restore.py"
V51 = ROOT / "tools" / "ai" / "state" / "memory_recall.py"
COMPARE_SCRIPT = HERE / "_phase5_vs_phase4_compare.py"
RUN_SCRIPT = HERE / "_phase5_run_benchmarks.py"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
MAPPING = {
    "memory_usage": "メモリ使用率",
    "cpu_temperature": "CPU温度",
    "disk_usage": "ディスク使用率",
    "gpu_usage": "GPUの使用率",
    "gpu_vram_usage": "GPU VRAM",
}


def case_of(run):
    req = run.get("request") or ""
    for k, v in MAPPING.items():
        if v in req:
            return k
    return "other"


def mtime(path: Path):
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def summarize_run_brief(run, idx):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    cb = pipe.get("context_budget_shadow") or {}
    calls = cb.get("calls") or []
    modes = {}
    for c in calls:
        m = c.get("recall_mode")
        if m:
            modes[m] = modes.get(m, 0) + 1
    hist = pipe.get("research_history")
    return {
        "idx": idx,
        "case": case_of(run),
        "timestamp": run.get("timestamp")
        or run.get("started_at")
        or run.get("created_at")
        or run.get("time"),
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "llm_calls": (run.get("timing") or {}).get("llm_calls"),
        "usable_findings": len(research.get("usable_findings") or []),
        "history_events": len(hist) if isinstance(hist, list) else None,
        "has_rounds_detail": bool(pipe.get("research_rounds_detail")),
        "has_judgments": bool(pipe.get("research_judgments") or pipe.get("judgments")),
        "recall_mode_counts": modes,
        "actual_headroom_min": (cb.get("summary") or {}).get("actual_headroom_min"),
        "headroom_gate_ok": (cb.get("summary") or {}).get("headroom_gate_ok"),
    }


def match_summary_to_runs(summary_item, candidates):
    """summary の主要スカラーで results 内 run を突き合わせる。"""
    keys = (
        "rounds",
        "llm_calls",
        "fail_stage",
        "actual_headroom_min",
        "pass",
    )
    hits = []
    for c in candidates:
        ok = True
        for k in keys:
            sv = summary_item.get(k)
            cv = c.get(k)
            if sv is None and cv is None:
                continue
            if sv != cv:
                ok = False
                break
        if ok:
            # recall modes soft match if present
            sm = summary_item.get("recall_mode_counts") or {}
            cm = c.get("recall_mode_counts") or {}
            if sm and cm and sm != cm:
                continue
            hits.append(c)
    return hits


def main():
    out = {
        "artifacts": {},
        "git": {
            "memory_recall_in_HEAD": False,
            "note": "tools/ai/state/memory_recall.py は untracked。Phase1-5 系は HEAD に未コミット。",
        },
        "env_from_scripts": {},
        "phase5_source_recovery": {},
        "results_json_linkage": {},
        "metric_coverage": {},
        "reproducibility_verdict": {},
    }

    for path in (SUMMARY, COMPARE, ANALYSIS, RESULTS, V5_RESTORE, V51, COMPARE_SCRIPT, RUN_SCRIPT):
        out["artifacts"][path.name] = {
            "exists": path.exists(),
            "mtime": mtime(path),
            "bytes": path.stat().st_size if path.exists() else None,
        }

    # env from scripts (static read)
    out["env_from_scripts"] = {
        "phase5_run_benchmarks": {
            "AI_AGENT_MEMORY_RECALL": "1",
            "AI_AGENT_MEMORY_JUDGE": "0",
            "AI_AGENT_CONTEXT_ALLOC_LIVE": "1 (setdefault)",
            "AI_AGENT_CONTEXT_ALLOC_SHADOW": "1 (setdefault)",
            "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1 (setdefault)",
            "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE": "3 (setdefault)",
            "cases": CASES,
            "entry": "research/llm_benchmarks/research_implement.py",
        },
        "phase5_vs_phase4_compare": {
            "phase4_live": {"AI_AGENT_MEMORY_RECALL": "0", "common": "same as above + MEMORY_JUDGE=0"},
            "phase5_recall": {"AI_AGENT_MEMORY_RECALL": "1", "common": "same"},
            "note": "同一スクリプト連続実行。seed / model temperature 固定なし。",
        },
    }

    # Phase 5 source
    out["phase5_source_recovery"] = {
        "git_commit": None,
        "transcript_write_restored_file": str(V5_RESTORE.name),
        "restored_exists": V5_RESTORE.exists(),
        "restored_bytes": V5_RESTORE.stat().st_size if V5_RESTORE.exists() else None,
        "current_on_disk": "Phase 5.1 (assess_information_gain / pivot)"
        if V51.exists() and "assess_information_gain" in V51.read_text(encoding="utf-8")
        else "unknown",
        "can_re_run_phase5_logic": V5_RESTORE.exists(),
        "caveat": "トランスクリプトから復元したソースは当時の1スナップショット。その後の小修正があれば欠落しうる。",
    }

    # Compare / summary content limits
    if COMPARE.exists():
        cmp = json.loads(COMPARE.read_text(encoding="utf-8"))
        sample = next(iter((cmp.get("phase4_live") or {}).values()), {})
        out["artifacts"]["_phase5_vs_phase4_compare.json"]["stores_full_history"] = False
        out["artifacts"]["_phase5_vs_phase4_compare.json"]["stored_metric_keys"] = sorted(
            sample.keys()
        )
        out["artifacts"]["_phase5_vs_phase4_compare.json"]["missing_for_5_1_eval"] = [
            "research_history",
            "research_rounds_detail",
            "judgments / missing loops raw",
            "error_class_recurrence",
            "command_family_recurrence",
            "no_gain_loop",
            "pivot_required / usable after pivot",
            "run timestamps / model / seed",
        ]

    if SUMMARY.exists():
        summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
        out["artifacts"]["_phase5_benchmark_summary.json"]["cases"] = [
            {
                "case": s.get("case"),
                "rounds": s.get("rounds"),
                "llm_calls": s.get("llm_calls"),
                "fail_stage": s.get("fail_stage"),
                "usable_findings": s.get("usable_findings"),
                "recall_mode_counts": s.get("recall_mode_counts"),
                "actual_headroom_min": s.get("actual_headroom_min"),
            }
            for s in summary
        ]

    if ANALYSIS.exists():
        an = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        # structure: cases is list or dict?
        cases = an.get("cases")
        out["artifacts"]["_phase5_1_repetition_analysis.json"]["has_waste_metrics"] = True
        out["artifacts"]["_phase5_1_repetition_analysis.json"]["has_no_gain"] = (
            "no_gain" in json.dumps(an)[:50000]
        )
        out["artifacts"]["_phase5_1_repetition_analysis.json"]["has_pivot"] = (
            "pivot" in json.dumps(an).lower()
        )
        if isinstance(cases, dict):
            out["artifacts"]["_phase5_1_repetition_analysis.json"]["case_ids"] = list(
                cases.keys()
            )
        elif isinstance(cases, list):
            out["artifacts"]["_phase5_1_repetition_analysis.json"]["case_ids"] = [
                c.get("case") for c in cases if isinstance(c, dict)
            ]

    # Link results.json
    linkage = {
        "results_exists": RESULTS.exists(),
        "run_count": None,
        "matched_phase5_summary": {},
        "matched_compare_phase4": {},
        "matched_compare_phase5": {},
        "raw_runs_usable_for_reanalysis": False,
    }
    if RESULTS.exists():
        data = json.loads(RESULTS.read_text(encoding="utf-8"))
        runs = data.get("runs") or []
        linkage["run_count"] = len(runs)
        briefs = [summarize_run_brief(r, i) for i, r in enumerate(runs)]
        by_case = {c: [b for b in briefs if b["case"] == c] for c in CASES}

        if SUMMARY.exists():
            for item in json.loads(SUMMARY.read_text(encoding="utf-8")):
                case = item["case"]
                hits = match_summary_to_runs(item, by_case.get(case) or [])
                linkage["matched_phase5_summary"][case] = {
                    "hit_count": len(hits),
                    "hits": hits[-3:],
                }

        if COMPARE.exists():
            cmp = json.loads(COMPARE.read_text(encoding="utf-8"))
            for label, bucket_key in (
                ("phase4_live", "matched_compare_phase4"),
                ("phase5_recall", "matched_compare_phase5"),
            ):
                for case, item in (cmp.get(label) or {}).items():
                    # build pseudo summary for matching
                    pseudo = {
                        "rounds": item.get("rounds"),
                        "llm_calls": item.get("llm_calls"),
                        "fail_stage": item.get("fail_stage"),
                        "actual_headroom_min": item.get("actual_headroom_min"),
                        "pass": item.get("pass"),
                        "recall_mode_counts": item.get("recall_mode_counts") or {},
                    }
                    hits = match_summary_to_runs(pseudo, by_case.get(case) or [])
                    linkage[bucket_key][case] = {
                        "hit_count": len(hits),
                        "hits": hits[-2:],
                    }

        # any recent run with history?
        with_hist = [b for b in briefs if (b.get("history_events") or 0) > 0]
        linkage["runs_with_history"] = len(with_hist)
        linkage["last_10"] = briefs[-10:]
        linkage["raw_runs_usable_for_reanalysis"] = len(with_hist) > 0

    out["results_json_linkage"] = linkage

    # Metric coverage matrix
    wanted = [
        "error_class_recurrence",
        "no_gain_loop",
        "command_family_recurrence",
        "open_question_loop",
        "pivot_then_usable_increase",
        "rounds",
        "llm_calls",
        "headroom",
        "result_fail_stage",
    ]
    coverage = {}
    for m in wanted:
        coverage[m] = {
            "in_compare_json": m
            in (
                "rounds",
                "llm_calls",
                "headroom",
                "result_fail_stage",
            ),  # headroom as actual_headroom_min; result as pass/fail_stage
            "in_phase5_summary": m
            in ("rounds", "llm_calls", "headroom", "result_fail_stage"),
            "in_repetition_analysis": m
            in (
                "error_class_recurrence",
                "command_family_recurrence",
                "open_question_loop",
                "rounds",
                "result_fail_stage",
            ),
            "needs_live_rerun_or_raw_history": m
            in (
                "no_gain_loop",
                "pivot_then_usable_increase",
            )
            or (
                m
                in (
                    "error_class_recurrence",
                    "command_family_recurrence",
                    "open_question_loop",
                )
                and not linkage.get("raw_runs_usable_for_reanalysis")
            ),
        }
    # refine: analysis has family/error/open_q for p4/p5 pair already
    coverage["error_class_recurrence"]["in_repetition_analysis"] = True
    coverage["command_family_recurrence"]["in_repetition_analysis"] = True
    coverage["open_question_loop"]["in_repetition_analysis"] = True
    coverage["no_gain_loop"]["in_repetition_analysis"] = False
    coverage["pivot_then_usable_increase"]["note"] = (
        "Phase 5.1 導入前の run には pivot_required が無い。5.1 は新規実行が必要。"
    )
    out["metric_coverage"] = coverage

    # Verdict
    p5_source_ok = V5_RESTORE.exists()
    raw_hist = bool(linkage.get("raw_runs_usable_for_reanalysis"))
    out["reproducibility_verdict"] = {
        "identical_conditions_three_way_live": {
            "possible": True,
            "how": (
                "MEMORY_RECALL=0 / =1+v5ソース / =1+v5.1ソース を同一スクリプト・同一 env 共通部で連続実行。"
                " v5 ソースはトランスクリプト復元を tools/ai/state に切替。"
            ),
            "not_identical_to_saved_runs": True,
            "reason": "LLM 非決定性 + 保存 run と新規 run は別試行。因果断定不可。",
        },
        "reuse_saved_p4_p5_as_baseline_for_p51_only_rerun": {
            "possible_partial": True,
            "have_scalar_p4_p5": COMPARE.exists(),
            "have_waste_p4_p5": ANALYSIS.exists(),
            "have_raw_history_for_deeper_recompute": raw_hist,
            "missing": [
                "no_gain_loop（当時未定義）",
                "pivot後usable（5.1専用）",
                "Git 上の Phase5 commit（無し）",
                "model/seed/temperature の記録",
            ],
        },
        "git_phase5_commit": {
            "exists": False,
            "implication": "checkout によるビット一致再現は不可。ソースはトランスクリプト復元のみ。",
        },
        "recommended_next_step": (
            "正式な三条件ライブ比較を行うなら: (1) v5 復元モジュールを env 切替で固定、"
            "(2) 生 pipeline（history/rounds_detail）を比較 JSON に保存、"
            "(3) 1試行のみで因果断定せず観測として報告。"
            " または保存 P4/P5（compare+analysis）を参照基線とし、P5.1 のみ新規実行して"
            "『同条件ではない参照比較』と明示する。"
        ),
        "phase5_source_recoverable": p5_source_ok,
        "saved_pair_p4_p5_scalars": COMPARE.exists(),
        "saved_pair_p4_p5_waste_taxonomy": ANALYSIS.exists(),
    }

    out_path = HERE / "_phase5_1_repro_investigation.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["reproducibility_verdict"], ensure_ascii=False, indent=2))
    print("\nWrote", out_path)


if __name__ == "__main__":
    main()
