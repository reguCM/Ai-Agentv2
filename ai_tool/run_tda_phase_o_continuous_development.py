#!/usr/bin/env python3
"""Run Phase O continuous development evaluation (no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_o_continuous_development_harness import (
    facet_trace,
    run_phase_o_continuous,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_phase_o_continuous_development"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_o_continuous()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "judgment": result["judgment"],
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "metrics": result["metrics"],
        "walls": [{"id": w["id"], "at": w["at"], "bridged": w.get("bridged")} for w in result["walls"]],
        "what_passed": result["what_passed"],
        "facet_trace": facet_trace(result),
        "o5_judgment_needs": result["o5_judgment_needs"],
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
