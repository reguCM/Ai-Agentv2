#!/usr/bin/env python3
"""Run Web Tool Failure Diagnosis Automation Phase 4 (read-only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_failure_diagnosis_phase4 import engine_status, run_failure_diagnosis

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_failure_diagnosis_phase4"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_FAILURE_DIAGNOSIS_AUTOMATION_PHASE4.md"
MODEL_DOC = _REPO / "docs" / "ai_tool" / "project_audit" / "FAILURE_DIAGNOSIS_MODEL.md"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _write_doc(result: dict[str, Any], status: dict[str, Any], run_id: str) -> None:
    summary = result.get("failure_case_summary") or {}
    lines = [
        "# Web Tool Failure Diagnosis Automation — Phase 4",
        "",
        f"**Run:** `{run_id}`",
        f"**Git HEAD:** `{_git_head()}`",
        "**Production changes:** NONE | **Git commit:** NONE",
        "",
        "## Engine status",
        "",
        json.dumps(status, ensure_ascii=False, indent=2),
        "",
        "## Failure case detection",
        "",
        json.dumps(summary.get("cases_detected") or {}, ensure_ascii=False, indent=2),
        "",
        "## Boundary design (deterministic vs LLM vs Human)",
        "",
        json.dumps(result.get("boundary_design") or {}, ensure_ascii=False, indent=2),
        "",
        "## Generalization assessment",
        "",
        json.dumps(result.get("generalization_assessment") or {}, ensure_ascii=False, indent=2),
        "",
        "## Diagnosis count",
        "",
        f"- Observations: {summary.get('observation_count', 0)}",
        f"- Diagnoses: {summary.get('diagnosis_count', 0)}",
        f"- All seven targets: {summary.get('all_seven_targets', False)}",
        "",
        "## Human review packet",
        "",
        "All proposals require Human Review before implementation.",
        "",
        f"Proposal count: {len(result.get('proposals') or [])}",
        "",
        "## STOP",
        "",
        "Implementation not performed. Diagnosis → Proposal → Human Review only.",
        "",
        "See also: [FAILURE_DIAGNOSIS_MODEL.md](./FAILURE_DIAGNOSIS_MODEL.md)",
    ]
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Web Tool Failure Diagnosis Phase 4 - starting ({RUN_ID})")

    result = run_failure_diagnosis()
    result["run_id"] = RUN_ID
    result["git_head"] = _git_head()
    status = engine_status(result)
    result["engine_status"] = status

    (RUN_DIR / "observations.json").write_text(
        json.dumps(result["observations"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "diagnosis.json").write_text(
        json.dumps(result["diagnoses"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "diagnoses_by_observation.json").write_text(
        json.dumps(result["diagnoses_by_observation"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "proposals.json").write_text(
        json.dumps(result["proposals"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "human_review_packet.json").write_text(
        json.dumps(result["human_review_packet"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "failure_case_summary.json").write_text(
        json.dumps(result["failure_case_summary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "full_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_doc(result, status, RUN_ID)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_tool_failure_diagnosis_phase4.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest_output.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(json.dumps({"run_id": RUN_ID, "engine_status": status, "pytest_exit": proc.returncode}, ensure_ascii=False, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
