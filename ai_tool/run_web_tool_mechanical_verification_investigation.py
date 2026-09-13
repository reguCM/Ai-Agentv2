#!/usr/bin/env python3
"""Run Mechanical Verification Investigation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_mechanical_verification_investigation import (
    run_mechanical_verification_investigation,
)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_mechanical_verification"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_mechanical_verification_investigation()
    result["run_id"] = RUN_ID

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_tool_mechanical_verification_investigation.py",
            "tests/ai_tool/project_audit/test_web_tool_success_class_accuracy_evaluation.py",
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
                "conclusion": result.get("conclusion"),
                "selected_option": result.get("selected_option"),
                "metrics": result.get("metrics"),
                "production_changes": result.get("production_changes"),
                "experimental_changes": result.get("experimental_changes"),
                "overall": result.get("overall"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "architecture_options.json").write_text(
        json.dumps(result.get("architecture_options") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "conclusion": result.get("conclusion"),
                "pass_rate": (result.get("metrics") or {}).get("scenario_pass_rate"),
                "fp": (result.get("metrics") or {}).get("false_positive_count"),
                "fn": (result.get("metrics") or {}).get("false_negative_count"),
                "pytest": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
