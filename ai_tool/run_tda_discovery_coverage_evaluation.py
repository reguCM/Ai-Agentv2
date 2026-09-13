#!/usr/bin/env python3
"""Run Phase N+2 — Facet Discovery coverage (no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_n2_discovery_coverage_harness import (
    run_phase_n2,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_discovery_coverage"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_n2()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_changed": False,
        "adoption": result["adoption"],
        "metrics": result["metrics"],
        "still_miss_gcr": result["still_miss_gcr"],
        "core_creation_gate": result["core_creation_gate"],
        "followup_chain": {
            "python_kept": result["followup_chain"]["python_kept"],
            "cuda_kept": result["followup_chain"]["cuda_not_overwritten_by_python"],
            "last_no_decision": result["followup_chain"]["last_no_decision"],
            "continuity": result["followup_chain"]["continuity"],
        },
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
