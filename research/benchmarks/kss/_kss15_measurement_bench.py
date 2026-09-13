"""
KSS-1.5 live measurement: kept/dropped 実測 + 人手監査セット生成。

observation-only。routing / filter 変更なし。
ベンチ専用 preflight で正しい Python（.venv + ollama）を強制する。
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
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_PATH = ROOT / "research" / "llm_benchmarks" / "research_implement_results.json"
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "knowledge_source_obs"
ENTRY = ROOT / "research" / "llm_benchmarks" / "research_implement.py"
INVALID_RUN_DIR = OUT_DIR / "kss15_20260820_160149"

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]
SNIPPET = {
    "memory_usage": "メモリ使用率",
    "cpu_temperature": "CPU温度",
    "disk_usage": "ディスク使用率",
    "gpu_usage": "GPUの使用率",
    "gpu_vram_usage": "GPU VRAM",
}

COMMON = {
    "AI_AGENT_CONTEXT_ALLOC_LIVE": "1",
    "AI_AGENT_CONTEXT_ALLOC_SHADOW": "1",
    "AI_AGENT_GLOBAL_JUDGE_LIVE_SKIP": "1",
    "AI_AGENT_GLOBAL_JUDGE_AUDIT_RATE": "3",
    "AI_AGENT_MEMORY_JUDGE": "0",
    "AI_AGENT_MEMORY_RECALL": "0",
    "AI_AGENT_MEMORY_RECALL_VERSION": "none",
    "AI_AGENT_KNOWLEDGE_SOURCE_OBS": "1",
    "AI_AGENT_KSS1_OBS": "0",
    "AI_AGENT_KSS11_OBS": "1",
    "AI_AGENT_KSS12_OBS": "1",
    "AI_AGENT_KSS13_OBS": "1",
    "AI_AGENT_KSS14_OBS": "1",
    "AI_AGENT_KSS15_OBS": "1",
    "AI_AGENT_KSS14_ANSWER_JUDGE": "0",
}


class BenchPreflightError(RuntimeError):
    pass


def resolve_bench_python():
    """
    既存成功ベンチと同じ実行系を優先。新しい venv は作らない。
    優先: AI_AGENT_BENCH_PYTHON → .venv → 現在の sys.executable（ollama 可なら）
    """
    candidates = []
    env_py = os.environ.get("AI_AGENT_BENCH_PYTHON")
    if env_py and str(env_py).strip():
        candidates.append(Path(env_py.strip()))
    candidates.append(ROOT / ".venv" / "Scripts" / "python.exe")
    candidates.append(ROOT / ".venv" / "bin" / "python")
    candidates.append(Path(sys.executable))

    checked = []
    for cand in candidates:
        info = {"path": str(cand), "exists": cand.is_file()}
        if not cand.is_file():
            checked.append(info)
            continue
        probe = subprocess.run(
            [
                str(cand),
                "-c",
                (
                    "import sys; print(sys.executable); print(sys.version); "
                    "import ollama; print(getattr(ollama,'__version__','missing')); "
                    "print(ollama.__file__)"
                ),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        info["returncode"] = probe.returncode
        info["stdout"] = (probe.stdout or "").strip()
        info["stderr"] = (probe.stderr or "").strip()[:400]
        checked.append(info)
        if probe.returncode == 0 and info["stdout"]:
            lines = info["stdout"].splitlines()
            return {
                "python_executable": lines[0].strip(),
                "python_version": lines[1].strip() if len(lines) > 1 else "missing",
                "ollama_available": True,
                "ollama_version": lines[2].strip() if len(lines) > 2 else "missing",
                "ollama_file": lines[3].strip() if len(lines) > 3 else "missing",
                "candidates_checked": checked,
            }
    return {
        "python_executable": "missing",
        "python_version": "missing",
        "ollama_available": False,
        "ollama_version": "missing",
        "ollama_file": "missing",
        "candidates_checked": checked,
    }


def preflight(python_info):
    """必須依存が欠ける場合は即停止（0件測定を生成しない）。"""
    errors = []
    if not python_info.get("ollama_available"):
        errors.append("ollama_import_failed")
    exe = python_info.get("python_executable")
    if not exe or exe == "missing" or not Path(exe).is_file():
        errors.append("python_executable_missing")

    if errors:
        raise BenchPreflightError(
            "BENCH_PREFLIGHT_FAILED: "
            + ",".join(errors)
            + " | candidates="
            + json.dumps(python_info.get("candidates_checked") or [], ensure_ascii=False)
        )

    # Research 依存 + feature flags（選択した Python で確認）
    check = subprocess.run(
        [
            exe,
            "-c",
            (
                "import os, sys\n"
                "os.environ['AI_AGENT_KSS15_OBS']='1'\n"
                "from tools.ai.llm.context_allocation import RESERVED_HEADROOM_CHARS\n"
                "from tools.system.tool_builder.research import web as web_mod\n"
                "from tools.ai.state.web_hit_partition import kss15_obs_enabled\n"
                "assert int(RESERVED_HEADROOM_CHARS) >= 800\n"
                "assert hasattr(web_mod, 'search_web')\n"
                "assert hasattr(web_mod, 'filter_relevant_hits')\n"
                "assert kss15_obs_enabled()\n"
                "print('preflight_ok')\n"
                "print(RESERVED_HEADROOM_CHARS)\n"
            ),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT), **COMMON},
    )
    if check.returncode != 0 or "preflight_ok" not in (check.stdout or ""):
        raise BenchPreflightError(
            "BENCH_PREFLIGHT_FAILED: research_deps_or_flags | "
            + (check.stderr or check.stdout or "")[:800]
        )
    return {
        "ok": True,
        "python_executable": exe,
        "python_version": python_info.get("python_version"),
        "ollama_available": True,
        "ollama_version": python_info.get("ollama_version"),
        "ollama_file": python_info.get("ollama_file"),
        "project_root": str(ROOT),
        "working_directory": str(ROOT),
        "feature_flags": dict(COMMON),
        "web_search_module": "tools.system.tool_builder.research.web",
        "stdout": (check.stdout or "").strip(),
    }


def mark_invalid_previous_run():
    """ollama 未導入の0件ベンチを本測定から除外。"""
    if not INVALID_RUN_DIR.exists():
        return None
    summary_path = INVALID_RUN_DIR / "summary.json"
    payload = {}
    if summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "measurement_invalid": True,
            "measurement_ok": False,
            "reason": "wrong_python_interpreter",
            "invalid_detail": (
                "Ran with system/default Python lacking ollama; "
                "no live research / no kept-dropped partition. "
                "Do not mix into KSS-1.5 success/fail rates."
            ),
            "human_audit_entries": 0,
            "not_a_research_failure": True,
            "not_a_web_search_failure": True,
            "not_evidence_of_zero_dropped_hits": True,
        }
    )
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    note = INVALID_RUN_DIR / "INVALID_MEASUREMENT.md"
    note.write_text(
        "\n".join(
            [
                "# INVALID MEASUREMENT",
                "",
                "- measurement_invalid: true",
                "- reason: wrong_python_interpreter",
                "- Do not treat as Research/Web/dropped=0 evidence.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(INVALID_RUN_DIR)


def match_case(request, case):
    return SNIPPET.get(case, case) in (request or "")


def extract_case_record(run, case):
    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    details = pipe.get("research_rounds_detail") or []
    rounds = []
    live_search_executed = False
    searches_observed = 0
    hits_observed = 0
    kept_hits = 0
    dropped_hits = 0
    dropped_state = "missing"  # missing | zero | positive

    for item in details:
        part = item.get("web_hit_partition")
        if isinstance(part, dict) and part.get("records"):
            from tools.ai.state.web_hit_partition import enrich_partition_with_heuristic

            part = enrich_partition_with_heuristic(
                part,
                request_text=run.get("request") or "",
                case_id=case,
            )
        if isinstance(part, dict) and part.get("source") == "live_web_exec":
            live_search_executed = True
            searches_observed += int(part.get("total_searches") or 0) or len(
                part.get("searches") or []
            )
            records = part.get("records")
            if isinstance(records, list):
                hits_observed += len(records)
                kept_hits += sum(1 for r in records if r.get("kept") is True)
                dropped_hits += sum(1 for r in records if r.get("kept") is False)
            dropped_list = part.get("dropped_hits")
            if isinstance(dropped_list, list):
                if len(dropped_list) == 0 and dropped_state != "positive":
                    dropped_state = "zero"
                elif len(dropped_list) > 0:
                    dropped_state = "positive"
            elif dropped_list == "missing" and dropped_state == "missing":
                dropped_state = "missing"

        rounds.append(
            {
                "round": item.get("round"),
                "web_hit_partition": part,
                "exploration_value_observation": item.get(
                    "exploration_value_observation"
                ),
                "information_loss_observation": item.get(
                    "information_loss_observation"
                ),
                "candidate_count": item.get("candidate_count"),
                "satisfies_request": item.get("satisfies_request"),
            }
        )

    timing = run.get("timing") or {}
    cb = (pipe.get("context_budget_shadow") or {}).get("summary") or {}
    valid_for_kss15 = bool(live_search_executed) and any(
        isinstance((r.get("web_hit_partition") or {}).get("records"), list)
        for r in rounds
    )
    return {
        "case": case,
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "stop_reason": research.get("stop_reason"),
        "request": run.get("request"),
        "rounds": rounds,
        "metrics": {
            "pass": run.get("pass"),
            "fail_stage": run.get("fail_stage"),
            "rounds": research.get("rounds"),
            "llm_calls": timing.get("llm_calls"),
            "actual_headroom_min": cb.get("actual_headroom_min"),
            "headroom_gate_ok": cb.get("headroom_gate_ok"),
            "live_search_executed": live_search_executed,
            "searches_observed": searches_observed,
            "hits_observed": hits_observed,
            "kept_hits": kept_hits,
            "dropped_hits": dropped_hits
            if dropped_state != "missing"
            else "missing",
            "dropped_hits_state": dropped_state,
            "dropped_observed": dropped_state in ("zero", "positive"),
            "valid_for_kss15_measurement": valid_for_kss15,
            "behavior_changed": False,
        },
        "pipeline": pipe,
        "timing": timing,
    }


def write_report(summary, metrics, dataset, out_path: Path):
    env = summary.get("environment") or {}
    lines = [
        "# KSS-1.5 Discarded Web Hit Live Audit",
        "",
        f"- experiment_id: `{summary.get('experiment_id')}`",
        f"- measurement_ok: `{summary.get('measurement_ok')}`",
        f"- measurement_invalid: `{summary.get('measurement_invalid')}`",
        f"- python_executable: `{env.get('python_executable')}`",
        f"- python_version: `{env.get('python_version')}`",
        f"- ollama_available: `{env.get('ollama_available')}`",
        f"- ollama_file: `{env.get('ollama_file')}`",
        f"- invalid_run_count: `{summary.get('invalid_run_count')}`",
        f"- label_source: `{metrics.get('label_source')}`",
        "",
        "## Required counts",
        "",
    ]
    for key in (
        "cases_total",
        "cases_completed",
        "cases_failed",
        "cases_valid_for_measurement",
        "searches_observed",
        "hits_observed",
        "total_searches",
        "total_hits",
        "kept_hits",
        "dropped_hits",
        "failed_runs",
        "successful_runs",
        "kept_with_direct",
        "kept_with_core",
        "kept_with_lead",
        "dropped_with_direct",
        "dropped_with_core",
        "dropped_with_lead",
        "dropped_answer_presence_unknown",
        "failed_runs_with_answer_in_dropped",
        "failed_runs_with_answer_in_kept",
        "failed_runs_with_no_answer_found",
    ):
        lines.append(f"- {key}: {(summary.get('run_stats') or metrics).get(key, metrics.get(key))}")
    lines.extend(
        [
            "",
            f"- four_group_counts: `{json.dumps(metrics.get('four_group_counts'), ensure_ascii=False)}`",
            f"- dropped_answer_rate: {metrics.get('dropped_answer_rate')}",
            "",
            "## drop_reason × answer_presence",
            "",
            f"```json\n{json.dumps(metrics.get('drop_reason_x_answer_presence'), ensure_ascii=False, indent=2)}\n```",
            "",
            "## Lead continuation",
            "",
            f"```json\n{json.dumps(metrics.get('lead_continuation'), ensure_ascii=False, indent=2)}\n```",
            "",
            "## Notes on dropped_hits",
            "",
            "- `dropped_hits = 0` ≠ no answers in dropped (none were dropped).",
            "- `dropped_hits = missing` ≠ zero; partition not observed.",
            "- `live_search_executed = false` is a separate invalid/incomplete state.",
            "",
            "## Human audit",
            "",
            f"- entries: {len(dataset.get('entries') or [])}",
            f"- buckets: `{json.dumps(dataset.get('bucket_counts'), ensure_ascii=False)}`",
            "",
            f"- routing_ready: False — {summary.get('routing_readiness_reason')}",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    invalid_marked = mark_invalid_previous_run()

    print("=== KSS-1.5 environment discovery ===", flush=True)
    python_info = resolve_bench_python()
    print(json.dumps(python_info, ensure_ascii=False, indent=2), flush=True)
    print(f"project_root: {ROOT}", flush=True)

    try:
        env_meta = preflight(python_info)
    except BenchPreflightError as exc:
        print(str(exc), flush=True)
        # 0件の測定ディレクトリは作らない
        sys.exit(2)

    print("=== PREFLIGHT OK ===", flush=True)
    print(f"sys.executable (bench runner may differ): {sys.executable}", flush=True)
    print(f"bench python: {env_meta['python_executable']}", flush=True)
    print(f"python_version: {env_meta['python_version']}", flush=True)
    print(f"ollama: {env_meta['ollama_file']}", flush=True)

    from tools.ai.state.web_hit_partition import (
        build_human_audit_dataset,
        compute_kss15_metrics,
        write_human_audit_markdown,
    )

    python_exe = env_meta["python_executable"]
    os.environ["AI_AGENT_KSS15_OBS"] = "1"

    exp_id = "kss15_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "purpose": "KSS-1.5 live kept/dropped + human audit dataset",
        "routing": False,
        "filter_changed": False,
        "llm_judge": False,
        "common_env": COMMON,
        "cases": cases,
        "trials": args.trials,
        "environment": env_meta,
        "supersedes_invalid_run": invalid_marked,
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    case_records = []
    for trial in range(1, args.trials + 1):
        for case in cases:
            before = (
                len(json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("runs", []))
                if RESULTS_PATH.exists()
                else 0
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            env.update(COMMON)
            env["AI_AGENT_RESEARCH_IMPLEMENT_CASE"] = case
            env["AI_AGENT_EXPERIMENT_ID"] = exp_id
            env["AI_AGENT_EXPERIMENT_CONDITION"] = "kss15_live"
            env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
            env["AI_AGENT_EXPERIMENT_CASE"] = case
            print(f"\n=== {exp_id} | live | trial={trial} | {case} ===", flush=True)
            print(f"  python={python_exe}", flush=True)
            proc = subprocess.run(
                [python_exe, str(ENTRY)], cwd=str(ROOT), env=env
            )
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            matched = [
                r
                for r in data.get("runs", [])[before:]
                if match_case(r.get("request"), case)
            ]
            if not matched:
                rec = {
                    "case": case,
                    "trial": trial,
                    "error": "NOT_FOUND",
                    "rounds": [],
                    "metrics": {
                        "valid_for_kss15_measurement": False,
                        "live_search_executed": False,
                        "dropped_hits_state": "missing",
                    },
                }
            else:
                rec = extract_case_record(matched[-1], case)
                rec["trial"] = trial
                rec["returncode"] = proc.returncode
            case_records.append(rec)
            (exp_dir / f"kss15__{case}__trial{trial}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            m = rec.get("metrics") or {}
            print(
                f"  -> pass={m.get('pass')} fail_stage={m.get('fail_stage')} "
                f"rounds={m.get('rounds')} live_search={m.get('live_search_executed')} "
                f"dropped_state={m.get('dropped_hits_state')} "
                f"valid={m.get('valid_for_kss15_measurement')} "
                f"headroom={m.get('actual_headroom_min')}",
                flush=True,
            )

    valid_cases = [
        c
        for c in case_records
        if (c.get("metrics") or {}).get("valid_for_kss15_measurement")
    ]
    metrics = compute_kss15_metrics(valid_cases, prefer_human=True)
    dataset = build_human_audit_dataset(valid_cases)

    searches_observed = sum(
        int((c.get("metrics") or {}).get("searches_observed") or 0)
        for c in valid_cases
    )
    hits_observed = sum(
        int((c.get("metrics") or {}).get("hits_observed") or 0) for c in valid_cases
    )
    kept_sum = sum(int((c.get("metrics") or {}).get("kept_hits") or 0) for c in valid_cases)
    dropped_sum = sum(
        int((c.get("metrics") or {}).get("dropped_hits") or 0)
        for c in valid_cases
        if (c.get("metrics") or {}).get("dropped_hits") != "missing"
    )
    any_dropped_missing = any(
        (c.get("metrics") or {}).get("dropped_hits_state") == "missing"
        for c in valid_cases
    )

    run_stats = {
        "cases_total": len(case_records),
        "cases_completed": sum(
            1 for c in case_records if c.get("error") != "NOT_FOUND"
        ),
        "cases_failed": sum(
            1
            for c in case_records
            if c.get("error") == "NOT_FOUND" or c.get("pass") is False
        ),
        "cases_valid_for_measurement": len(valid_cases),
        "searches_observed": searches_observed,
        "hits_observed": hits_observed,
        "kept_hits": kept_sum,
        "dropped_hits": "missing" if (not valid_cases and any_dropped_missing) else dropped_sum,
    }

    measurement_ok = len(valid_cases) > 0 and searches_observed > 0
    summary = {
        "experiment_id": exp_id,
        "phase": "kss-1.5",
        "measurement_ok": measurement_ok,
        "measurement_invalid": False,
        "invalid_run_count": 1 if invalid_marked else 0,
        "invalid_runs_excluded": [invalid_marked] if invalid_marked else [],
        "not_for_decision": True,
        "routing_implemented": False,
        "environment": env_meta,
        "run_stats": run_stats,
        "metrics": metrics,
        "per_case": [
            {
                "case": c.get("case"),
                "pass": c.get("pass"),
                "fail_stage": c.get("fail_stage"),
                "stop_reason": c.get("stop_reason"),
                "live_search_executed": (c.get("metrics") or {}).get(
                    "live_search_executed"
                ),
                "dropped_hits_state": (c.get("metrics") or {}).get(
                    "dropped_hits_state"
                ),
                "valid_for_kss15_measurement": (c.get("metrics") or {}).get(
                    "valid_for_kss15_measurement"
                ),
                "error": c.get("error"),
            }
            for c in case_records
        ],
        "human_audit_bucket_counts": dataset.get("bucket_counts"),
        "routing_readiness_reason": (
            "Need filled human labels + more trials; no routing."
        ),
        "missing_items": [
            "human_answer_presence (until worksheet filled)",
            "llm_human_agreement (deferred)",
            "full page text beyond snippet",
        ],
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (exp_dir / "human_audit_dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_human_audit_markdown(dataset, exp_dir / "human_audit_worksheet.md")
    write_report(summary, metrics, dataset, exp_dir / "report.md")

    print(f"\nWrote {exp_dir}", flush=True)
    print("MEASUREMENT_OK:", measurement_ok, flush=True)
    print("python_executable:", env_meta["python_executable"], flush=True)
    print("ollama_available:", True, flush=True)
    print("cases_total:", run_stats["cases_total"], flush=True)
    print("cases_completed:", run_stats["cases_completed"], flush=True)
    print("cases_failed:", run_stats["cases_failed"], flush=True)
    print("searches_observed:", searches_observed, flush=True)
    print("hits_observed:", hits_observed, flush=True)
    print("kept_hits:", kept_sum, flush=True)
    print("dropped_hits:", run_stats["dropped_hits"], flush=True)
    print("invalid_run_count:", summary["invalid_run_count"], flush=True)
    print("HUMAN_AUDIT_ENTRIES:", len(dataset.get("entries") or []), flush=True)
    print("ROUTING_READY: False", flush=True)


if __name__ == "__main__":
    main()
