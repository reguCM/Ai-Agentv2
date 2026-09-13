#!/usr/bin/env python3
"""Run LLM-Centered Web Research Architecture Adoption (Model B operating model)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.normal_development_defensive_core import run_normal_development_defensive_core

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_llm_centered_web_research_architecture_adoption"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_normal_development_defensive_core(fetch_live=False)
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_normal_development_defensive_core.py",
            "tests/ai_tool/project_audit/test_defensive_core_discovery_policy.py",
            "-q",
            "--tb=no",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    result["pytest_exit"] = proc.returncode
    result["pytest_output"] = proc.stdout + proc.stderr

    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "final_decision": result.get("final_decision"),
                "decisions": result.get("decisions"),
                "overall": result.get("overall"),
                "production_changes": result.get("production_changes"),
                "what_we_did_not_build": result.get("what_we_did_not_build"),
                "track_b_report_table": (result.get("track_b") or {}).get("report_table"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "phase": result.get("phase"),
                "overall": result.get("overall"),
                "decisions": result.get("decisions"),
                "current_problem": (result.get("track_a") or {}).get("current_problem"),
                "new_c3_created": (result.get("track_b") or {}).get("new_c3_created"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("overall") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
