#!/usr/bin/env python3
"""Observation Tool Specification Phase 2 — validate v2 drafts, no production changes."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TOOL_CREATION = _REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_observation_spec_phase2"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID

V2_SPECS = [
    TOOL_CREATION / "specs" / "get_gpu_status_v2_draft.json",
    TOOL_CREATION / "specs" / "get_gpu_processes_v2_draft.json",
    TOOL_CREATION / "specs" / "cpu_status_v2_draft.json",
    TOOL_CREATION / "specs" / "get_cpu_status_v2_draft.json",
]


def validate_specs() -> list[dict]:
    from validator.validate import validate_tool_spec_file

    rows: list[dict] = []
    for path in V2_SPECS:
        result = validate_tool_spec_file(path)
        rows.append({"spec": path.name, "verdict": result.verdict, "details": result.to_dict()})
    return rows


def run_pytest() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/tool_creation/test_observation_spec_v2_draft.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    git_branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=_REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=_REPO, text=True)

    validation = validate_specs()
    pytest_result = run_pytest()

    all_accept = all(r["verdict"] == "ACCEPT" for r in validation)
    tests_pass = pytest_result["returncode"] == 0

    evaluation = {
        "phase": "observation_spec_phase2",
        "overall": "COMPLETE" if all_accept and tests_pass else "FAILED",
        "validator_all_accept": all_accept,
        "pytest_pass": tests_pass,
        "production_code_changed": False,
        "registry_changed": False,
        "agent_changed": False,
        "human_review_required": True,
        "stop": "HUMAN REVIEW REQUIRED",
        "v2_specs": [p.name for p in V2_SPECS],
        "human_review_doc": "docs/ai_tool/project_audit/OBSERVATION_SPEC_HUMAN_REVIEW.md",
    }

    report = {
        "git_head": git_head,
        "git_branch": git_branch,
        "validation_results": validation,
        "pytest": pytest_result,
        "evaluation": evaluation,
        "prior_audit_run": "runs/ai_tool/20260828_172810_observation_capability_audit",
        "recommendations": {
            "get_gpu_status": "REPAIR (WT measured) + v2 spec formalize",
            "get_gpu_processes": "KEEP v2 contract",
            "cpu_status": "KEEP legacy LoadPercentage",
            "get_cpu_status": "NEW tool draft — NOT_IMPLEMENTED",
            "provider_strategy": "A (single tool + internal provider)",
        },
    }

    (RUN_DIR / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "git_state.txt").write_text(f"HEAD: {git_head}\nbranch: {git_branch}\n\n{git_status}", encoding="utf-8")
    append_audit({"event": "observation_spec_phase2", "run_dir": str(RUN_DIR), "evaluation": evaluation}, log_path=RUN_DIR / "audit.jsonl")

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0 if all_accept and tests_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
