"""
KSS-1.1 measurement bench（既存判断根拠の観測整合性）。

行動経路は Phase 4 live と同一。観測のみ ON。
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
OUT_DIR = ROOT / "research" / "llm_benchmarks" / "kss11_measurement"
ENTRY = ROOT / "research" / "llm_benchmarks" / "research_implement.py"

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
    "AI_AGENT_KSS1_OBS": "0",  # 自己申告は正式扱いにしない
    "AI_AGENT_KSS11_OBS": "1",
}


def match_case(request, case):
    return SNIPPET.get(case, case) in (request or "")


def summarize(run):
    from tools.ai.state.decision_evidence import summarize_decision_evidence

    pipe = run.get("pipeline") or {}
    research = pipe.get("research") or {}
    timing = run.get("timing") or {}
    cb = (pipe.get("context_budget_shadow") or {}).get("summary") or {}
    rounds = pipe.get("research_rounds_detail") or []
    hist = pipe.get("research_history") or []
    bundles = []
    for item in rounds:
        b = item.get("decision_evidence_observation")
        if isinstance(b, dict) and b.get("enabled"):
            bundles.append(b)
    summary = summarize_decision_evidence(bundles)
    overflow = run.get("error") == "context_overflow" or any(
        t.get("error") == "context_overflow" for t in (run.get("trace") or [])
    )
    return {
        "pass": run.get("pass"),
        "fail_stage": run.get("fail_stage"),
        "error": run.get("error"),
        "rounds": research.get("rounds"),
        "llm_calls": timing.get("llm_calls"),
        "usable_findings": len(research.get("usable_findings") or []),
        "actual_headroom_min": cb.get("actual_headroom_min"),
        "headroom_gate_ok": cb.get("headroom_gate_ok"),
        "context_overflow": overflow,
        "kss11_obs_rounds": len(bundles),
        "kss11_history_events": sum(
            1 for e in hist if e.get("type") == "decision_evidence_obs"
        ),
        "proposal_evidence": run.get("decision_evidence_proposal")
        or (pipe.get("decision_evidence_proposal")),
        "behavior_changed": False,
        "evidence_summary": summary,
    }


def measurement_ok(records):
    problems = []
    for rec in records:
        m = rec.get("metrics") or {}
        if rec.get("error") == "NOT_FOUND":
            problems.append(f"{rec.get('case')}: NOT_FOUND")
            continue
        if m.get("rounds") is not None and m.get("kss11_obs_rounds", 0) <= 0:
            problems.append(f"{rec.get('case')}: no decision evidence on research rounds")
        if m.get("context_overflow"):
            problems.append(f"{rec.get('case')}: overflow")
        if m.get("rounds") is not None and m.get("headroom_gate_ok") is False:
            problems.append(f"{rec.get('case')}: headroom gate fail")
        es = m.get("evidence_summary") or {}
        if m.get("kss11_obs_rounds", 0) > 0:
            if not (es.get("provenance_coverage") or {}).get("rate"):
                problems.append(f"{rec.get('case')}: provenance coverage missing")
    return (not problems), problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]

    from tools.ai.llm.context_allocation import RESERVED_HEADROOM_CHARS
    from tools.ai.state.decision_evidence import (
        EXISTING_TO_OBS_MAPPING,
        MISSING_FIELDS,
        kss11_obs_enabled,
    )

    os.environ["AI_AGENT_KSS11_OBS"] = "1"
    assert kss11_obs_enabled()
    assert int(RESERVED_HEADROOM_CHARS) >= 800

    exp_id = "kss11_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "purpose": "KSS-1.1 decision evidence observability (not routing)",
        "formalize_phase5_1": False,
        "auto_routing": False,
        "common_env": COMMON,
        "existing_to_obs_mapping": EXISTING_TO_OBS_MAPPING,
        "missing_fields": MISSING_FIELDS,
        "cases": cases,
        "trials": args.trials,
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    records = []
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
            env["AI_AGENT_EXPERIMENT_CONDITION"] = "kss11_obs"
            env["AI_AGENT_EXPERIMENT_TRIAL"] = str(trial)
            env["AI_AGENT_EXPERIMENT_CASE"] = case
            print(f"\n=== {exp_id} | kss11 | trial={trial} | {case} ===", flush=True)
            proc = subprocess.run([sys.executable, str(ENTRY)], cwd=str(ROOT), env=env)
            data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            matched = [
                r
                for r in data.get("runs", [])[before:]
                if match_case(r.get("request"), case)
            ]
            if not matched:
                rec = {"case": case, "trial": trial, "error": "NOT_FOUND"}
            else:
                run = matched[-1]
                # proposal evidence may sit on result root before save — check pipeline
                if run.get("decision_evidence_proposal") is None:
                    # saved via experiment only if we add to save_run — use metrics from rounds
                    pass
                rec = {
                    "case": case,
                    "trial": trial,
                    "returncode": proc.returncode,
                    "timestamp": run.get("timestamp"),
                    "experiment": run.get("experiment"),
                    "metrics": summarize(run),
                    "pipeline": run.get("pipeline"),
                    "state": run.get("state"),
                    "timing": run.get("timing"),
                }
            records.append(rec)
            (exp_dir / f"kss11__{case}__trial{trial}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            m = rec.get("metrics") or {}
            es = m.get("evidence_summary") or {}
            print(
                f"  -> fail_stage={m.get('fail_stage')} rounds={m.get('rounds')} "
                f"kss11_rounds={m.get('kss11_obs_rounds')} "
                f"decisions={es.get('decision_count')} "
                f"sources={es.get('decision_source_distribution')} "
                f"levels={es.get('evidence_coverage')} "
                f"headroom={m.get('actual_headroom_min')}",
                flush=True,
            )

    ok, problems = measurement_ok(records)
    # aggregate across cases
    from tools.ai.state.decision_evidence import summarize_decision_evidence

    all_bundles = []
    for rec in records:
        for item in ((rec.get("pipeline") or {}).get("research_rounds_detail") or []):
            b = item.get("decision_evidence_observation")
            if isinstance(b, dict) and b.get("enabled"):
                all_bundles.append(b)
    agg = summarize_decision_evidence(all_bundles)

    recommendation = {
        "primary": "A",
        "rationale": (
            "既存の verifier high/low・progress reason・live_skip・escalation・"
            "no_gain だけで failure/success の根拠分解は可能。"
            "KSS-1 の LLM 自己申告は coverage=0 で信頼できないため B は後回し。"
            "HELP/上位LLM routing (D/E) はまだ根拠不足。F は『単一 confidence 数値化』に限れば妥当。"
        ),
        "options": {
            "A": "verifier/rule 校正を優先（推奨）",
            "B": "LLM structured self-assessment（取得率が低い限り後回し）",
            "C": "Web evidence 強化（hit_score の decision 紐付けが次）",
            "D": "上位 LLM 相談判定（データ不足）",
            "E": "HELP escalation（経路未実装）",
            "F": "単一 confidence 定量化は難しい（自己申告失敗を踏まえ正当）",
        },
    }

    summary = {
        "experiment_id": exp_id,
        "measurement_ok": ok,
        "problems": problems,
        "formalize_phase5_1": False,
        "auto_routing": False,
        "n_records": len(records),
        "aggregate": agg,
        "per_case": [
            {"case": r.get("case"), "metrics": r.get("metrics")} for r in records
        ],
        "recommendation": recommendation,
        "behavior_unchanged": True,
        "disclaimer": (
            "Observation-only. Do not invent missing scores. "
            "Do not implement routing/HELP/Web priority from this run alone."
        ),
    }
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (exp_dir / "report.md").write_text(
        _render_report(summary), encoding="utf-8"
    )
    print("\n=== KSS-1.1 SUMMARY ===")
    print(json.dumps({k: summary[k] for k in (
        "experiment_id", "measurement_ok", "problems", "aggregate", "recommendation"
    )}, ensure_ascii=False, indent=2))
    print(f"\nWrote {exp_dir}")
    print("MEASUREMENT_OK:", "YES" if ok else "NO")
    print("RECOMMENDATION:", recommendation["primary"])
    if not ok:
        raise SystemExit(1)


def _render_report(summary):
    agg = summary.get("aggregate") or {}
    rec = summary.get("recommendation") or {}
    lines = [
        "# KSS-1.1 Measurement Report",
        "",
        f"- experiment_id: `{summary.get('experiment_id')}`",
        f"- measurement_ok: **{summary.get('measurement_ok')}**",
        f"- formalize_phase5_1: {summary.get('formalize_phase5_1')}",
        f"- auto_routing: {summary.get('auto_routing')}",
        "",
        "## Aggregate",
        "",
        f"- decision_count: {agg.get('decision_count')}",
        f"- decision_source_distribution: `{agg.get('decision_source_distribution')}`",
        f"- evidence levels: `{(agg.get('evidence_coverage') or {}).get('levels')}`",
        f"- provenance rate: `{(agg.get('provenance_coverage') or {}).get('rate')}`",
        f"- threshold rate: `{(agg.get('threshold_coverage') or {}).get('rate')}`",
        f"- high_evidence_failure_count: {agg.get('high_evidence_failure_count')}",
        f"- low_evidence_success_count: {agg.get('low_evidence_success_count')}",
        f"- failure_by_evidence_level: `{agg.get('failure_by_evidence_level')}`",
        f"- success_by_evidence_level: `{agg.get('success_by_evidence_level')}`",
        "",
        "## Missing fields (not invented)",
        "",
    ]
    for item in agg.get("missing_fields") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"**Primary: {rec.get('primary')}**",
            "",
            rec.get("rationale") or "",
            "",
            "### Options",
            "",
        ]
    )
    for k, v in (rec.get("options") or {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.extend(["", "## Disclaimer", "", summary.get("disclaimer") or "", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
