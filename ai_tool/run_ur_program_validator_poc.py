#!/usr/bin/env python3
"""Run Phase H — URScript Validator + URSim Boundary PoC."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.experimental.ur_program_validator.harness import run_phase_h_poc

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_ur_program_validator_poc"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_phase_h_poc()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ai_tool/experimental/test_ur_program_validator_poc.py",
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
                "decision": result.get("decision"),
                "pass_count": result.get("pass_count"),
                "total": result.get("total"),
                "critical_misses": len(result.get("critical_misses") or []),
                "ursim_mode": result.get("ursim_probe", {}).get("mode"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Phase H UR Validator: {result.get('pass_count')}/{result.get('total')} PASS")
    print(f"Decision: {result.get('decision')}")
    print(f"URSim mode: {result.get('ursim_probe', {}).get('mode')}")
    print(f"Run dir: {RUN_DIR}")
    return 0 if result.get("decision") == "POC_BOUNDARY_CONFIRMED" and proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
