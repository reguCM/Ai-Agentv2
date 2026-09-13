#!/usr/bin/env python3
"""Run Phase N+1 — Generalized Facet Discovery (no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_n1_generalized_facet_harness import run_phase_n1

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_generalized_facet_discovery"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_n1()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "production_changes": 0,
        "new_c3": 0,
        "metrics": result["metrics"],
        "adoption": result["adoption"],
        "failures": result["failures"],
        "domains_evaluated": result["domains_evaluated"],
        "workflow_insertion": result["workflow_insertion"]["recommended"],
        "core_creation_gate": result["core_creation_gate"],
    }
    (RUN_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    print(f"wrote {RUN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
