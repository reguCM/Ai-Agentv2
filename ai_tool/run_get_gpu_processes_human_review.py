#!/usr/bin/env python3
"""get_gpu_processes HEAD vs Working Tree — Human Review Phase (read-only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_get_gpu_processes_human_review"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
HEAD = "88febb3"
MIGRATION_RUN = _REPO / "runs" / "ai_tool" / "20260828_163325_get_gpu_processes_migration"
LEGACY_AUDIT_RUN = _REPO / "runs" / "ai_tool" / "20260828_161848_legacy_tool_audit"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=_REPO, text=True).strip()


def _head_gpu_processes_source() -> str:
    return _git("show", f"{HEAD}:tools/system/gpu/gpu_processes.py")


def _working_tree_gpu_processes_source() -> str:
    return (_REPO / "tools/system/gpu/gpu_processes.py").read_text(encoding="utf-8")


def _registry_entry() -> dict:
    reg = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    return next(t for t in reg["tools"] if t["name"] == "get_gpu_processes")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    head_src = _head_gpu_processes_source()
    wt_src = _working_tree_gpu_processes_source()
    reg = _registry_entry()

    migration_comparison = {}
    if (MIGRATION_RUN / "comparison.json").exists():
        migration_comparison = json.loads((MIGRATION_RUN / "comparison.json").read_text(encoding="utf-8"))

    difference_matrix = [
        {
            "item": "return_type",
            "head": "list",
            "working_tree": "dict (processes, ok, status, error, observation_source, source)",
            "classification": "INTERFACE_CHANGE",
        },
        {
            "item": "data_source",
            "head": "hardcoded static list",
            "working_tree": "nvidia-smi --query-compute-apps via query_gpu_processes()",
            "classification": "IMPROVEMENT + BEHAVIOR_CHANGE",
        },
        {
            "item": "process_count",
            "head": "always 2 (ollama, python.exe)",
            "working_tree": "0..N from observation",
            "classification": "BEHAVIOR_CHANGE",
        },
        {
            "item": "pid",
            "head": "NOT_RETURNED",
            "working_tree": "integer or \"unknown\" per process",
            "classification": "INTERFACE_CHANGE",
        },
        {
            "item": "name",
            "head": "short name strings (ollama, python.exe)",
            "working_tree": "nvidia-smi process_name (full path or [Insufficient Permissions])",
            "classification": "BEHAVIOR_CHANGE",
        },
        {
            "item": "vram_used",
            "head": "fixed integers (4500, 1200)",
            "working_tree": "integer MiB or \"unknown\" ([N/A] not coerced to 0)",
            "classification": "IMPROVEMENT + BEHAVIOR_CHANGE",
        },
        {
            "item": "fixed_values",
            "head": "YES — ollama/python stub",
            "working_tree": "NO — fixed fallback prohibited",
            "classification": "IMPROVEMENT",
        },
        {
            "item": "ok/status/error",
            "head": "NOT_RETURNED (never fails)",
            "working_tree": "ok, status, error fields",
            "classification": "INTERFACE_CHANGE",
        },
        {
            "item": "observation_source",
            "head": "NOT_RETURNED",
            "working_tree": "always \"real\"",
            "classification": "INTERFACE_CHANGE",
        },
        {
            "item": "error_behavior",
            "head": "no error path",
            "working_tree": "nvidia-smi missing → ok=false, processes=[], status=unavailable",
            "classification": "BEHAVIOR_CHANGE",
        },
        {
            "item": "change_intent",
            "head": "UNKNOWN — no docstring",
            "working_tree": "docstring states real observation intent",
            "classification": "UNKNOWN",
        },
    ]

    compatibility = {
        "input": "COMPATIBLE",
        "output": "CHANGED",
        "semantic": "CHANGED",
        "error": "CHANGED",
        "safety": "COMPATIBLE",
        "agent": "COMPATIBLE",
        "registry": "CHANGED",
        "test": "CHANGED",
        "notes": {
            "agent": "execute_tool passes raw result; summarize handles dict. No list-specific agent logic found.",
            "registry": "working tree registry adds visibility=agent, observation_source=real, nvidia-smi description — separate uncommitted diff from gpu_processes.py",
            "test": "test_gpu_real_observation + migration tests expect dict/working-tree contract; HEAD revert would fail them",
            "in_repo_consumers": "No production code iterates list return directly (grep static analysis)",
        },
    }

    head_revert_impact = {
        "gpu_processes.py_only": [
            "Returns fake ollama/python list again",
            "Migration spec get_gpu_processes_legacy_migrated.json contradicts HEAD",
            "tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py would fail",
            "tests/test_gpu_real_observation.py::test_processes_not_fixed_ollama_python would fail",
        ],
        "registry_working_tree_without_impl": [
            "Registry description claims nvidia-smi real observation while HEAD impl is stub — MISMATCH",
        ],
    }

    adopt_working_tree_impact = {
        "positive": [
            "Aligns with Registry working-tree description (nvidia-smi, observation_source=real)",
            "Matches get_gpu_status real-observation pattern",
            "Migration spec/tests/audit evidence already based on working tree",
            "33/33 pid independent observation PASS (migration run 20260828_163325)",
        ],
        "risks": [
            "INTERFACE_CHANGE: list → dict breaks hypothetical external list consumers (none found in repo)",
            "BEHAVIOR_CHANGE: process list content no longer fixed ollama/python",
            "VRAM per-process often unknown — PARTIAL observation (documented)",
        ],
    }

    comparison = {
        "head_commit": HEAD,
        "head_implementation_summary": {
            "return": "list[{name, vram_used}]",
            "observation": "HARDCODED_STUB",
            "error_semantics": "none",
        },
        "working_tree_implementation_summary": {
            "return": "dict with processes[], ok, status, error, observation_source, source",
            "observation": "nvidia-smi compute-apps REAL (VRAM PARTIAL)",
            "error_semantics": "empty processes + ok=false on failure",
        },
        "difference_matrix": difference_matrix,
        "independent_observation_ref": str(MIGRATION_RUN / "comparison.json"),
        "independent_observation": migration_comparison,
        "legacy_audit_ref": str(LEGACY_AUDIT_RUN),
    }

    evaluation = {
        "review_scope": "get_gpu_processes.py HEAD vs working tree only",
        "excluded_from_decision": "unrelated working tree changes (research/, other tools/, etc.)",
        "interface_compatibility": "CHANGED",
        "semantic_compatibility": "CHANGED",
        "safety_compatibility": "COMPATIBLE",
        "behavior_compatibility": "CHANGED",
        "recommended_decision": "ADOPT_WORKING_TREE",
        "recommended_decision_rationale": [
            "HEAD is demonstrably hardcoded stub contradicting Tool purpose and Registry working-tree description",
            "Working tree has verified nvidia-smi observation path and migration contract tests",
            "Safety unchanged; Agent path compatible with dict return",
            "INTERFACE_CHANGE (list→dict) requires human acknowledgment — no in-repo list consumers found",
        ],
        "human_decision": "PENDING",
        "alternative_decisions": {
            "KEEP_HEAD": "Would preserve list stub; contradicts Registry WT description and migration artifacts",
            "REBUILD_FROM_SPEC": "Not indicated — working tree matches formalized legacy_migrated spec",
            "DEFER": "If external list consumers exist outside repo — evidence insufficient to defer",
        },
        "safety_gates": {
            "unsafe_accept": 0,
            "wrong_file_inclusion": 0,
            "secret_inclusion": 0,
            "allowlist_violation": 0,
        },
        "production_code_changed_this_phase": False,
        "registry_changed_this_phase": False,
        "agent_changed_this_phase": False,
        "commit_executed": False,
        "stop": True,
        "stop_reason": "HUMAN DECISION REQUIRED",
    }

    inputs = {
        "experiment": "get_gpu_processes_human_review",
        "git_branch": _git("branch", "--show-current"),
        "git_head": _git("rev-parse", "HEAD"),
        "review_target_path": "tools/system/gpu/gpu_processes.py",
        "head_baseline_commit": HEAD,
        "related_runs": [str(MIGRATION_RUN.name), str(LEGACY_AUDIT_RUN.name)],
    }

    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "head_gpu_processes.py").write_text(head_src, encoding="utf-8")
    (RUN_DIR / "working_tree_gpu_processes.py").write_text(wt_src, encoding="utf-8")
    (RUN_DIR / "registry_entry_working_tree.json").write_text(
        json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "head_revert_impact.json").write_text(
        json.dumps(head_revert_impact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "adopt_working_tree_impact.json").write_text(
        json.dumps(adopt_working_tree_impact, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    append_audit(
        {"event": "get_gpu_processes_human_review", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# get_gpu_processes Human Review Run",
                "",
                f"- HEAD: `{HEAD}`",
                f"- recommended_decision: **{evaluation['recommended_decision']}**",
                f"- human_decision: **{evaluation['human_decision']}**",
                f"- STOP: **YES — HUMAN DECISION REQUIRED**",
                "",
                "See `docs/ai_tool/tool_creation/GET_GPU_PROCESSES_HUMAN_REVIEW.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
