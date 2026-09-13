#!/usr/bin/env python3
"""Run Web Tool Web-Status evaluation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_web_status_evaluation import run_web_status_evaluation

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_web_status_evaluation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    result = run_web_status_evaluation()
    result["run_id"] = RUN_ID
    result["git_head"] = _git_head()
    (RUN_DIR / "full_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_tool_web_status_evaluation.py",
            "-q",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    print(json.dumps({"run_id": RUN_ID, "summary": result["summary"], "pytest_exit": proc.returncode}, ensure_ascii=False))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
