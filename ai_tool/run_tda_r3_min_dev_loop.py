#!/usr/bin/env python3
"""R3：最小開発ループを実行する。Production と Cursor API は使わない。"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_r3_min_loop_harness import run_r3_min_dev_loop

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_r3_min_dev_loop"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_r3_min_dev_loop()
    result["run_id"] = RUN_ID
    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": RUN_ID,
        "judgment": result["judgment"],
        "experimental_mechanical": result["experimental_mechanical"],
        "item_results": result["item_results"],
        "fails": result["fails"],
        "first_failures": result["first_failures"],
        "metrics": result["metrics"],
        "production_changes": 0,
        "new_c3": 0,
        "standard_workflow_default_discovery": "off",
        "phase_f_decision": result["phase_f_decision"],
        "production_connect": (result.get("r314") or {}).get("production_connect"),
        "core_creation_gate": result["core_creation_gate"],
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
