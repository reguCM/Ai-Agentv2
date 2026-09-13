#!/usr/bin/env python3
"""Run Phase I-Live empirical Development Loop against official URSim 5.15.2."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.ur_program_validator.phase_i_live_harness import run_phase_i_live
from ai_tool.experimental.ur_program_validator.storage_policy import resolve_storage_root

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_ur_program_validator_phase_i_live"
RUN_DIR = resolve_storage_root(_REPO) / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_i_live(max_loop_attempts=2)
    result["run_id"] = RUN_ID

    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "decision": result.get("decision"),
                "production_changes": result.get("production_changes"),
                "golden_pass": result.get("golden_pass"),
                "dev_loop": (result.get("development_loop") or {}).get("decision"),
                "blind_spots": result.get("blind_spots"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "human_review.json").write_text(
        json.dumps(result.get("human_review") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Phase I-Live Decision: {result.get('decision')}")
    print(f"Dev loop: {(result.get('development_loop') or {}).get('decision')}")
    print(f"Golden: {result.get('golden_pass')} Production: {result.get('production_changes')}")
    print(f"Run dir: {RUN_DIR}")
    return 0 if result.get("decision") in (
        "LIVE_LOOP_CONFIRMED",
        "LIVE_LOOP_PARTIAL",
        "LIVE_LOOP_BLOCKED",
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
