#!/usr/bin/env python3
"""Run Web Tool Failure Analysis Phase 1 (read-only investigation)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_failure_analysis import (
    answer_final_questions,
    prioritized_fix_targets,
    run_failure_analysis,
)

REPO_ROOT = _REPO


def main() -> int:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / "runs" / "ai_tool" / f"{ts}_web_tool_failure_analysis"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Web Tool Failure Analysis Phase 1 - starting ({ts})")
    analysis = run_failure_analysis()
    analysis["run_timestamp"] = ts
    analysis["final_questions"] = answer_final_questions(analysis)
    analysis["fix_priorities"] = prioritized_fix_targets(analysis)

    out_path = run_dir / "analysis_summary.json"
    out_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    # Per-probe artifacts
    (run_dir / "search_probes.json").write_text(
        json.dumps(analysis["search_probes"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "fetch_probes.json").write_text(
        json.dumps(analysis["fetch_probes"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "hypotheses.json").write_text(
        json.dumps(analysis["hypotheses"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "final_questions.json").write_text(
        json.dumps(analysis["final_questions"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    grades = analysis.get("domain_grades") or {}
    print("\nDomain grades:")
    for k, v in grades.items():
        print(f"  {k}: {v}")
    print(f"\nArtifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
