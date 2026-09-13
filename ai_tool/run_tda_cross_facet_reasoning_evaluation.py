#!/usr/bin/env python3
"""Run Phase K — Local Cross-Facet Reasoning Evaluation (offline, no new Core)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.development_assistance.phase_k_cross_facet_harness import run_phase_k

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_cross_facet_reasoning"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_k()
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
        "reach": result["reach"],
        "core_creation_gate": result["core_creation_gate"],
        "center_case": result["center_case"],
        "k7_ja_reuse": result["k7_existing_consumers"]["ja"]["reuse"]["mode"],
        "k7_en_reuse": result["k7_existing_consumers"]["en"]["reuse"]["mode"],
        "k7_en_mentions_clear": result["k7_existing_consumers"]["en"]["mentions_clear_operational_mode"],
        "k8_names": result["k8_idea_discovery"]["names_seen"],
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
