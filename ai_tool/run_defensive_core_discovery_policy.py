#!/usr/bin/env python3
"""Run Defensive Core Discovery Policy integration."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.defensive_core_discovery_policy import run_defensive_core_discovery_policy_integration

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_defensive_core_discovery_policy"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_defensive_core_discovery_policy_integration()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/ai_tool/project_audit/test_defensive_core_discovery_policy.py",
            "tests/ai_tool/agent_integration/test_eval_production_parity_bridge.py",
            "tests/ai_tool/project_audit/test_web_tool_evaluation_canonical_migration.py",
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
    report = result.get("mandatory_phase_report") or {}
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "policy_adoption": result.get("policy_adoption"),
                "phase_decisions": result.get("phase_decisions"),
                "overall": result.get("overall"),
                "production_changes": result.get("production_changes"),
                "future_core_track": report.get("future_core_track"),
                "existing_core_usage": {
                    "total_reuse_count": (report.get("existing_core_usage") or {}).get("total_reuse_count"),
                    "cc01_reuse_count": (report.get("existing_core_usage") or {}).get("cc01_reuse_count"),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "core_registry.json").write_text(
        json.dumps((report.get("existing_core_usage") or {}).get("cores") or [], indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "policy_adoption": result.get("policy_adoption"),
                "decisions": result.get("phase_decisions"),
                "golden": result.get("golden_baseline"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("overall") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
