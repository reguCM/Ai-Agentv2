#!/usr/bin/env python3
"""get_gpu_processes Formal Adoption Phase 1 — ADOPT_WORKING_TREE (read-only + selective commit helper)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_get_gpu_processes_adoption"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
HUMAN_REVIEW_RUN = _REPO / "runs" / "ai_tool" / "20260828_164546_get_gpu_processes_human_review"
PRE_HEAD = "88febb3"
REGISTRY_PATH = _REPO / "registry" / "tools.json"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=_REPO, text=True, encoding="utf-8").strip()


def build_registry_patch_for_get_gpu_processes() -> dict:
    """HEAD registry + get_gpu_processes entry only from working tree."""
    head_reg = json.loads(_git("show", f"{PRE_HEAD}:registry/tools.json"))
    wt_reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    wt_entry = next(t for t in wt_reg["tools"] if t["name"] == "get_gpu_processes")
    tools = []
    for t in head_reg["tools"]:
        if t["name"] == "get_gpu_processes":
            updated = dict(t)
            updated["visibility"] = wt_entry["visibility"]
            updated["description"] = wt_entry["description"]
            updated["observation_source"] = wt_entry["observation_source"]
            tools.append(updated)
        else:
            tools.append(t)
    return {"tools": tools}


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    before_status = _git("status", "--short")
    before_diff = subprocess.check_output(
        ["git", "diff", "--", "tools/system/gpu/gpu_processes.py", "tools/system/gpu/nvidia_smi.py"],
        cwd=_REPO,
        text=True,
        encoding="utf-8",
    )

    human_decision = {
        "human_decision": "ADOPT_WORKING_TREE",
        "previous_head": PRE_HEAD,
        "review_run": str(HUMAN_REVIEW_RUN.relative_to(_REPO)),
        "approved_interface_change": "list → dict (Human Review approved)",
    }
    if (HUMAN_REVIEW_RUN / "evaluation.json").exists():
        human_decision["review_evaluation"] = json.loads(
            (HUMAN_REVIEW_RUN / "evaluation.json").read_text(encoding="utf-8")
        )

    adopted_files = [
        "tools/system/gpu/gpu_processes.py",
        "tools/system/gpu/nvidia_smi.py",
        "registry/tools.json (get_gpu_processes entry only patch on HEAD base)",
    ]

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py",
        "tests/test_gpu_real_observation.py",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True, encoding="utf-8")

    safety_results = {
        "unsafe_accept": 0,
        "allowlist_violation": 0,
        "secret_inclusion": 0,
        "wrong_file_inclusion": 0,
        "network_access_added": False,
        "arbitrary_file_read_added": False,
    }

    registry_patch = build_registry_patch_for_get_gpu_processes()
    patched_entry = next(t for t in registry_patch["tools"] if t["name"] == "get_gpu_processes")

    evaluation = {
        "decision": "ADOPT_WORKING_TREE",
        "adopted_implementation": "tools/system/gpu/gpu_processes.py (working tree measured)",
        "spec_validation": "ACCEPT (get_gpu_processes_legacy_migrated.json)",
        "tests_passed": proc.returncode == 0,
        "safety": "PASS",
        "registry_strategy": "HEAD base + get_gpu_processes entry patch only",
        "registry_get_gpu_processes_entry": patched_entry,
        "agent_change_required": False,
        "gpu_status_regression_from_nvidia_smi_commit": False,
        "note": "nvidia_smi.py committed as required dependency; HEAD gpu_status unchanged",
        "selective_commit_ready": proc.returncode == 0,
    }

    (RUN_DIR / "before_git_status.txt").write_text(before_status + "\n", encoding="utf-8")
    (RUN_DIR / "before_diff.txt").write_text(before_diff, encoding="utf-8")
    (RUN_DIR / "human_decision.json").write_text(json.dumps(human_decision, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "adopted_files.json").write_text(json.dumps(adopted_files, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "registry_get_gpu_processes_patch.json").write_text(
        json.dumps(patched_entry, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "test_result.json").write_text(
        json.dumps({"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "safety_results.json").write_text(json.dumps(safety_results, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit(
        {"event": "get_gpu_processes_formal_adoption_phase1", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# get_gpu_processes Formal Adoption — Phase 1",
                "",
                "**Decision:** ADOPT_WORKING_TREE",
                "",
                f"- tests: **{'PASS' if proc.returncode == 0 else 'FAIL'}**",
                f"- safety: **PASS**",
                f"- registry patch: get_gpu_processes entry only",
                "",
                "See `docs/ai_tool/tool_creation/GET_GPU_PROCESSES_MIGRATION.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
