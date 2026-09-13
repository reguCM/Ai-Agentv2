#!/usr/bin/env python3
"""Run Phase P-7〜P-12 memory redistribution (no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_p7_memory_redistribution_harness import (
    run_phase_p7_p12,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_phase_p7_memory_redistribution"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_p7_p12()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "judgment": result["judgment"],
        "item_results": result["item_results"],
        "metrics": result["metrics"],
        "p12": result["p12"],
        "p8_unresolved_without_id": result["p8"]["unresolved_without_id"],
        "overlap": {
            "unique_ok": result["overlap"]["unique_ok"],
            "ambiguous_unresolved": result["overlap"]["ambiguous_unresolved"],
        },
        "core_creation_gate": result["core_creation_gate"],
        "production_changes": 0,
        "new_c3": 0,
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
