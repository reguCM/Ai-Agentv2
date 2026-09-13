#!/usr/bin/env python3
"""Run Phase I-R — URSim Environment Recovery Investigation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.ur_program_validator.phase_i_r_harness import run_phase_i_r_investigation

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_ur_program_validator_phase_i_r"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_i_r_investigation()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ai_tool/experimental/test_ur_program_validator_phase_i_r.py",
            "-q",
            "--tb=no",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result["pytest_exit"] = proc.returncode
    result["pytest_output"] = proc.stdout + proc.stderr

    (RUN_DIR / "observations.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "decision": result.get("decision"),
                "live_mode": result.get("live_mode"),
                "recommended_path": result.get("deployment_decision", {}).get("recommended"),
                "requires_user_approval": result.get("deployment_decision", {}).get("requires_user_approval"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "human_recommendation.json").write_text(
        json.dumps(result.get("human_recommendation", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Phase I-R Decision: {result.get('decision')}")
    print(f"Live mode: {result.get('live_mode')}")
    rec = result.get("deployment_decision", {})
    print(f"Recommended: {rec.get('recommended', '')}")
    print(f"User approval required: {rec.get('requires_user_approval')}")
    print(f"Tests: {result.get('pass_count')}/{result.get('total')} (stub if live blocked)")
    print(f"Run dir: {RUN_DIR}")

    ok = result.get("decision") in (
        "LIVE_URSIM_CONFIRMED",
        "LIVE_URSIM_AUTOMATION_CONFIRMED",
        "LIVE_DEVELOPMENT_LOOP_CONFIRMED",
        "ENVIRONMENT_BLOCKED",
        "PENDING_USER_APPROVAL",
    )
    return 0 if ok and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
