"""
KSS-1.4 measurement: 経路分解 + discarded-hit 答え存在性（observation-only）。

既定は KSS-1.3 実験ディレクトリからの offline 再構築。
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
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = ROOT / "research" / "llm_benchmarks" / "knowledge_source_obs"
DEFAULT_SRC = (
    ROOT
    / "research"
    / "llm_benchmarks"
    / "knowledge_source_obs"
    / "kss13_20260820_154524"
)

CASES = [
    "memory_usage",
    "cpu_temperature",
    "disk_usage",
    "gpu_usage",
    "gpu_vram_usage",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-from", default=str(DEFAULT_SRC))
    parser.add_argument("--cases", default=",".join(CASES))
    args = parser.parse_args()
    cases = [c.strip() for c in args.cases.split(",") if c.strip()]
    src = Path(args.offline_from)

    from tools.ai.state.information_loss import build_trajectory
    from tools.ai.state.web_answer_presence import audit_round_answer_presence
    from research.llm_benchmarks.kss14_analyze import analyze_experiment_dir, write_report

    exp_id = "kss14_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    exp_dir = OUT_DIR / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "experiment_id": exp_id,
        "purpose": "KSS-1.4 information loss + discarded hit answer audit",
        "mode": "offline_rebuild",
        "offline_from": str(src),
        "routing": False,
        "confidence_threshold": False,
        "web_force": False,
        "answer_judge": "web_answer_presence_heuristic (LLM judge OFF)",
        "cases": cases,
    }
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for path in sorted(src.glob("*.json")):
        if path.name in ("summary.json", "manifest.json"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        case = rec.get("case")
        if case not in cases:
            for c in cases:
                if f"__{c}__" in path.name:
                    case = c
                    rec["case"] = c
                    break
            else:
                continue
        pipe = rec.get("pipeline") or {}
        metrics = rec.get("metrics") or {}
        details = pipe.get("research_rounds_detail") or []
        k13 = [
            d.get("exploration_value_observation")
            for d in details
            if isinstance(d.get("exploration_value_observation"), dict)
            and d["exploration_value_observation"].get("enabled")
        ]
        traj = build_trajectory(
            case_id=case,
            rounds_kss13=k13 or None,
            round_details=details,
            final_pass=metrics.get("pass", rec.get("pass")),
            fail_stage=metrics.get("fail_stage", rec.get("fail_stage")),
            fail_reason=rec.get("error")
            or (pipe.get("research") or {}).get("stop_reason"),
            stop_reason=(pipe.get("research") or {}).get("stop_reason"),
            research_run_id=exp_id,
        )
        request = rec.get("request") or ""
        for i, item in enumerate(details):
            audit = audit_round_answer_presence(
                request_text=request,
                case_id=case,
                web_hit_partition=item.get("web_hit_partition"),
                round_item=item,
            )
            rob = {}
            if i < len(traj.get("round_observations") or []):
                rob = dict(traj["round_observations"][i])
            rob["web_answer_presence_audit"] = audit
            rob["enabled"] = True
            rob["phase"] = "kss-1.4"
            item["information_loss_observation"] = rob
            item["web_hit_partition"] = item.get("web_hit_partition") or {
                "kept_hits": item.get("web_hits") or [],
                "dropped_hits": "missing",
                "source": "saved_web_hits_only",
            }
        pipe["information_loss_trajectory"] = traj
        pipe["research_rounds_detail"] = details
        rec["pipeline"] = pipe
        rec["kss14_mode"] = "offline_rebuild"
        out = exp_dir / f"kss14__{case}__trial1.json"
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"  {case}: rounds={len(traj.get('rounds') or [])} "
            f"labels={(traj.get('run_loss_classification') or {}).get('labels')}",
            flush=True,
        )

    summary = analyze_experiment_dir(exp_dir)
    summary["experiment_id"] = exp_id
    summary["manifest"] = manifest
    (exp_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(summary, exp_dir / "report.md")
    print(f"\nWrote {exp_dir}")
    print(
        "ROUTING_READY:",
        (summary.get("routing_readiness") or {}).get("sufficient_for_routing_rules"),
    )


if __name__ == "__main__":
    main()
