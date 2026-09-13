#!/usr/bin/env python3
"""Run Web Tool Evaluation Canonical Migration evaluation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_evaluation_canonical_migration import run_web_tool_evaluation_canonical_migration

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_evaluation_canonical_migration"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_web_tool_evaluation_canonical_migration()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/ai_tool/agent_integration/test_eval_production_parity_bridge.py",
            "tests/ai_tool/project_audit/test_web_tool_practical_evaluation.py",
            "tests/ai_tool/project_audit/test_web_tool_end_to_end_evaluation_phase3.py",
            "tests/ai_tool/project_audit/test_web_tool_success_class_accuracy_evaluation.py",
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
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "decision": result.get("decision"),
                "overall": result.get("overall"),
                "migration": result.get("migration"),
                "golden_baseline": {
                    "overall": (result.get("golden_baseline") or {}).get("overall"),
                    "pass_count": (result.get("golden_baseline") or {}).get("pass_count"),
                },
                "cc01_assessment": result.get("cc01_assessment"),
                "production_changes": result.get("production_changes"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "decision": result.get("decision"),
                "golden": (result.get("golden_baseline") or {}).get("overall"),
                "migrated": sum(1 for h in (result.get("migration") or []) if h.get("status") == "migrated"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("overall") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
