#!/usr/bin/env python3
"""Run Core Capability Discovery Challenge."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core_capability_discovery_challenge import run_core_capability_discovery_challenge

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_core_capability_discovery_challenge"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_core_capability_discovery_challenge()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/ai_tool/project_audit/test_core_capability_discovery_challenge.py",
            "tests/ai_tool/project_audit/test_web_tool_mechanical_verification_investigation.py",
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
                "decisions": result.get("decisions"),
                "discovered_count": len(result.get("discovered_capabilities") or []),
                "specification_change_requests": result.get("specification_change_requests"),
                "production_changes": result.get("production_changes"),
                "overall": result.get("overall"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    caps = result.get("discovered_capabilities") or []
    (RUN_DIR / "capability_candidates.json").write_text(
        json.dumps(caps, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "decisions": result.get("decisions"),
                "candidates": len(caps),
                "scr": "YES" if result.get("specification_change_requests") != "NONE" else "NO",
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
