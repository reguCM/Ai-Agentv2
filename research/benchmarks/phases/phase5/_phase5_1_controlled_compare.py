"""
Phase 4 / 5 / 5.1 制御比較ベンチ。

方針:
  - 保存済み P4/P5 は参考基線（改変しない・因果断定しない）
  - 差分は Memory Recall Policy のみ
  - 複数試行・run metadata・完全 History 保存
  - Phase 5.1 は正式化しない（本スクリプトは観測用）

Usage:
  py -3.14 research/benchmarks/phases/phase5/_phase5_1_controlled_compare.py
  py -3.14 research/benchmarks/phases/phase5/_phase5_1_controlled_compare.py --trials 2
  py -3.14 research/benchmarks/phases/phase5/_phase5_1_controlled_compare.py --preflight-only
  py -3.14 research/benchmarks/phases/phase5/_phase5_1_controlled_compare.py --conditions phase4,phase5_1 --cases memory_usage
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
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
BASELINE_DIR = (
    ROOT / "research" / "llm_benchmarks" / "baselines" / "phase4_phase5_reference"
)
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "phase_compare_controlled"
ENTRY = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]

# 共通設定（条件間で変えない）
COMMON_ENV = {
    "AI_AGENT_CONTEXT_ALLOC_LIVE": "1",
    "AI_AGENT_CONTEXT_ALLOC_SHADOW": "1",
    "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1",
    "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE": "3",
    "AI_AGENT_MEMORY_JUDGE": "0",
}

CONDITIONS = {
    "phase4": {
        "label": "phase4_live",
        "AI_AGENT_MEMORY_RECALL": "0",
        # version は参照されないが記録のため明示
        "AI_AGENT_MEMORY_RECALL_VERSION": "none",
        "policy": "handoff_legacy_no_memory_recall",
    },
    "phase5": {
        "label": "phase5_rule_recall",
        "AI_AGENT_MEMORY_RECALL": "1",
        "AI_AGENT_MEMORY_RECALL_VERSION": "5",
        "policy": "rule_recall_command_key_error_class",
    },
    "phase5_1": {
        "label": "phase5_1_pivot_recall",
        "AI_AGENT_MEMORY_RECALL": "1",
        "AI_AGENT_MEMORY_RECALL_VERSION": "5.1",
        "policy": "error_class_family_open_question_no_gain_pivot",
    },
}

CASE_REQUEST_SNIPPET = {
    "memory_usage": "メモリ使用率",
    "cpu_temperature": "CPU温度",
    "disk_usage": "ディスク使用率",
    "gpu_usage": "GPUの使用率",
    "gpu_vram_usage": "GPU VRAM",
}


def match_case(request, case):
    return CASE_REQUEST_SNIPPET.get(case, case) in (request or "")


def sha256_file(path: Path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_pipeline_config():
    cfg = {}
    try:
        from tools.system.config import get_llm_profile, load_yaml

        pipe = load_yaml(ROOT / "config" / "pipeline.yaml") or {}
        profile = get_llm_profile()
        cfg = {
            "active_model": pipe.get("active_model"),
            "profile_id": profile.get("id") or pipe.get("active_model"),
            "model": profile.get("model"),
            "temperature": profile.get("temperature"),
            "num_predict": profile.get("num_predict"),
            "context_limit": profile.get("context_limit"),
        }
    except Exception as exc:
        cfg = {"error": str(exc)}
    return cfg


def preflight(conditions, cases, trials):
    """意図しない差分が無いか確認。問題があれば list[str]。"""
    problems = []
    if not ENTRY.exists():
        problems.append(f"missing entry: {ENTRY}")
    if not (ROOT / "tools" / "ai" / "state" / "memory_recall.py").exists():
        problems.append("missing memory_recall.py")
    if not (ROOT / "tools" / "ai" / "state" / "memory_recall_v5.py").exists():
        problems.append("missing memory_recall_v5.py (Phase 5 restore)")

    # baseline frozen
    for name in (
        "_phase5_vs_phase4_compare.json",
        "_phase5_benchmark_summary.json",
        "_phase5_1_repetition_analysis.json",
    ):
        frozen = BASELINE_DIR / name
        live = HERE / name
        if not frozen.exists():
            problems.append(f"baseline missing: {frozen}")
            continue
        if live.exists():
            if sha256_file(frozen) != sha256_file(live):
                problems.append(
                    f"baseline drift vs live copy: {name} "
                    "(reference dir must stay bit-identical to original snapshot)"
                )

    # version switch smoke
    os.environ["AI_AGENT_MEMORY_RECALL"] = "1"
    os.environ["AI_AGENT_MEMORY_RECALL_VERSION"] = "5"
    from tools.ai.state.memory_recall import (
        build_recall_bundle,
        memory_recall_policy_version,
    )
    from tools.ai.state.research_history import ResearchHistory
    from tools.ai.state.task_state import TaskState

    if memory_recall_policy_version() != "5":
        problems.append("MEMORY_RECALL_VERSION=5 did not select policy 5")
    state = TaskState(
        research_history=ResearchHistory.from_snapshot(
            [
                {
                    "id": "evt_a",
                    "type": "verify_fail",
                    "action": {"command": "powershell", "args": ["a"]},
                    "result": {"ok": False, "error": "empty"},
                    "metadata": {"round": 1},
                },
                {
                    "id": "evt_b",
                    "type": "verify_fail",
                    "action": {"command": "powershell", "args": ["a"]},
                    "result": {"ok": False, "error": "empty"},
                    "metadata": {"round": 2},
                },
            ]
        ),
        open_questions=[
            {
                "id": "q1",
                "text": "t",
                "status": "open",
                "related_events": ["evt_a", "evt_b"],
            }
        ],
    )
    b5 = build_recall_bundle(state)
    if (b5.get("policy_trace") or {}).get("phase") not in ("5", None):
        # v5 sets phase=5 after our patch
        pass
    if b5.get("mode") != "repeating":
        problems.append(f"phase5 policy expected repeating on cmd streak, got {b5.get('mode')}")

    os.environ["AI_AGENT_MEMORY_RECALL_VERSION"] = "5.1"
    if memory_recall_policy_version() != "5.1":
        problems.append("MEMORY_RECALL_VERSION=5.1 did not select policy 5.1")
    b51 = build_recall_bundle(state)
    if not b51.get("pivot_required") and b51.get("mode") != "repeating":
        problems.append(
            f"phase5.1 expected repeating/pivot on empty_sample streak, got mode={b51.get('mode')}"
        )

    # condition env uniqueness: only recall knobs differ
    keys_allowed_diff = {
        "AI_AGENT_MEMORY_RECALL",
        "AI_AGENT_MEMORY_RECALL_VERSION",
        "label",
        "policy",
    }
    for name in conditions:
        cond = CONDITIONS[name]
        for k, v in COMMON_ENV.items():
            if cond.get(k) not in (None, v) and k not in keys_allowed_diff:
                problems.append(f"{name} overrides common {k}={cond.get(k)} != {v}")

    cfg = load_pipeline_config()
    report = {
        "ok": not problems,
        "problems": problems,
        "cases": cases,
        "conditions": conditions,
        "trials": trials,
        "common_env": COMMON_ENV,
        "condition_envs": {c: CONDITIONS[c] for c in conditions},
        "pipeline": cfg,
        "entry": str(ENTRY),
        "baseline_dir": str(BASELINE_DIR),
        "note": (
            "Saved P4/P5 baselines are reference-only; "
            "do not treat them as same-trial as this controlled run."
        ),
        "formalize_phase5_1": False,
    }
    return report


def build_env(condition_name, *, experiment_id, trial, case):
    cond = CONDITIONS[condition_name]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.update(COMMON_ENV)
    env["AI_AGENT_MEMORY_RECALL"] = cond["AI_AGENT_MEMORY_RECALL"]
    env["AI_AGENT_MEMORY_RECALL_VERSION"] = cond["AI_AGENT_MEMORY_RECALL_VERSION"]
    env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
    env["AI_AGENT_EXPERIMENT_ID"] = experiment_id
    env["AI_AGENT_EXPERIMENT_CONDITION"] = condition_name
    env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
    env["AI_AGENT_EXPERIMENT_CASE"] = case
    return env


def run_one(condition_name, case, trial, experiment_id):
    before = 0
    if RESULTS_PATH.exists():
        before = len(json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", []))
    env = build_env(condition_name, experiment_id=experiment_id, trial=trial, case=case)
    print(
        f"\n=== {experiment_id} | {condition_name} | trial={trial} | {case} ===",
        flush=True,
    )
    proc = subprocess.run([sys.executable, str(ENTRY)], cwd=str(ROOT), env=env)
    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    new_runs = data.get("runs", [])[before:]
    matched = [r for r in new_runs if match_case(r.get("request"), case)]
    if not matched:
        return {
            "error": "NOT_FOUND",
            "returncode": proc.returncode,
            "condition": condition_name,
            "case": case,
            "trial": trial,
        }
    run = matched[-1]
    # attach full metadata (History already in pipeline)
    from research.llm_benchmarks.phase_compare_metrics import compute_compare_metrics

    metrics = compute_compare_metrics(run)
    return {
        "condition": condition_name,
        "condition_label": CONDITIONS[condition_name]["label"],
        "policy": CONDITIONS[condition_name]["policy"],
        "case": case,
        "trial": trial,
        "returncode": proc.returncode,
        "timestamp": run.get("timestamp"),
        "experiment": run.get("experiment"),
        "profile": run.get("profile"),
        "model": run.get("model"),
        "metrics": metrics,
        # History 完全保存（Prompt 削減と混同しない）
        "pipeline": run.get("pipeline"),
        "state": run.get("state"),
        "timing": run.get("timing"),
        "trace": run.get("trace"),
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "request": run.get("request"),
    }


def aggregate(records):
    """条件×ケースで試行平均（断定せず観測）。"""
    from collections import defaultdict

    groups = defaultdict(list)
    for rec in records:
        if rec.get("error") == "NOT_FOUND":
            continue
        key = (rec["condition"], rec["case"])
        groups[key].append(rec.get("metrics") or {})

    keys = [
        "rounds",
        "llm_calls",
        "usable_findings",
        "insufficient_findings",
        "repeat_same_command_rate",
        "repeat_same_error_class_rate",
        "repeat_same_command_family_rate",
        "repeated_open_question_rate",
        "no_gain_loop_rate",
        "pivot_required_count",
        "primary_waste_event_count",
        "actual_headroom_min",
        "defer_count",
    ]
    out = {}
    for (cond, case), items in groups.items():
        summary = {"condition": cond, "case": case, "n_trials": len(items)}
        for k in keys:
            vals = [m.get(k) for m in items if m.get(k) is not None]
            if not vals:
                summary[k] = {"mean": None, "values": []}
                continue
            try:
                fvals = [float(v) for v in vals]
                summary[k] = {
                    "mean": round(sum(fvals) / len(fvals), 3),
                    "values": fvals,
                }
            except (TypeError, ValueError):
                summary[k] = {"mean": None, "values": vals}
        # no_gain fraction
        ng = [1 if m.get("no_gain") else 0 for m in items]
        summary["no_gain_fraction"] = round(sum(ng) / len(ng), 3) if ng else None
        summary["pass_fraction"] = round(
            sum(1 if m.get("pass") else 0 for m in items) / len(items), 3
        )
        out[f"{cond}:{case}"] = summary
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument(
        "--conditions",
        default="phase4,phase5,phase5_1",
        help="comma list: phase4,phase5,phase5_1",
    )
    parser.add_argument(
        "--cases",
        default=",".join(CASES),
        help="comma list of cases",
    )
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="default: controlled_YYYYMMDD_HHMMSS",
    )
    args = parser.parse_args()
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    for c in conditions:
        if c not in CONDITIONS:
            raise SystemExit(f"unknown condition: {c}")
    for c in cases:
        if c not in CASES:
            raise SystemExit(f"unknown case: {c}")

    report = preflight(conditions, cases, args.trials)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    preflight_path = OUT_DIR / "preflight_last.json"
    preflight_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("=== PREFLIGHT ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["problems"]:
        print("PREFLIGHT_FAILED")
        raise SystemExit(1)
    print("PREFLIGHT_OK")
    if args.preflight_only:
        return

    experiment_id = args.experiment_id or (
        "controlled_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    exp_dir = OUT_DIR / experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "formalize_phase5_1": False,
        "reference_baseline_dir": str(BASELINE_DIR),
        "reference_baseline_note": (
            "Past P4/P5 runs are reference-only; not same-trial as this experiment."
        ),
        "common_env": COMMON_ENV,
        "conditions": {c: CONDITIONS[c] for c in conditions},
        "cases": cases,
        "trials": args.trials,
        "pipeline": load_pipeline_config(),
        "entry": str(ENTRY),
        "eval_focus": (
            "Reduce no-gain repetition of same error_class / "
            "open_question / command_family (not mere exact command repeats)."
        ),
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = []
    # 試行外側: 各 trial で全条件×全ケース（条件間の時間近接を保つ）
    for trial in range(1, args.trials + 1):
        for condition in conditions:
            for case in cases:
                rec = run_one(condition, case, trial, experiment_id)
                records.append(rec)
                out_name = f"{condition}__{case}__trial{trial}.json"
                (exp_dir / out_name).write_text(
                    json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                m = rec.get("metrics") or {}
                print(
                    f"  -> fail_stage={rec.get('fail_stage')} rounds={m.get('rounds')} "
                    f"no_gain={m.get('no_gain')} "
                    f"err_class_rate={m.get('repeat_same_error_class_rate')} "
                    f"family_rate={m.get('repeat_same_command_family_rate')} "
                    f"oq_rate={m.get('repeated_open_question_rate')} "
                    f"pivot={m.get('pivot_required_count')} "
                    f"headroom={m.get('actual_headroom_min')}",
                    flush=True,
                )

    summary = {
        "experiment_id": experiment_id,
        "formalize_phase5_1": False,
        "n_records": len(records),
        "aggregate": aggregate(records),
        "disclaimer": (
            "LLM non-determinism: do not claim causal superiority from one trial. "
            "Compare distributions across trials; reference baselines are separate past runs."
        ),
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== AGGREGATE (observational) ===")
    print(json.dumps(summary["aggregate"], ensure_ascii=False, indent=2))
    print(f"\nWrote {exp_dir}")
    print("FORMALIZE_PHASE5_1: NO (observational run only)")


if __name__ == "__main__":
    main()
