#!/usr/bin/env python3
"""Run Phase L — Relevant Facet Selection evaluation (no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_l_relevant_facet_harness import run_phase_l

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_relevant_facet_selection"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_l()
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
        "core_creation_gate": result["core_creation_gate"],
        "answer": result["answer"],
        "mode_c_better_than_b_on_suppression": result["mode_c_better_than_b_on_suppression"],
        "k9_conflict_reached": result["metrics"]["k9_conflict_reached"],
        "k9_min_facets_mode_c": result["metrics"]["k9_min_facets_mode_c"],
    }
    (RUN_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote {RUN_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
