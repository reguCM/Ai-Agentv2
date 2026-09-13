#!/usr/bin/env python3
"""get_gpu_processes Legacy → Current Migration Phase 1 — isolated run (read-only)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TOOL_CREATION = _REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_get_gpu_processes_migration"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
SPEC_PATH = TOOL_CREATION / "specs" / "get_gpu_processes_legacy_migrated.json"


def _parse_compute_apps_csv(stdout: str) -> list[dict[str, Any]]:
    rows = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        pid_raw = parts[0] if len(parts) > 0 else ""
        name = parts[1] if len(parts) > 1 else ""
        vram_raw = parts[2] if len(parts) > 2 else ""
        try:
            pid: Any = int(pid_raw)
        except (TypeError, ValueError):
            pid = pid_raw or None
        vram: Any
        if vram_raw.lower() in ("[n/a]", "n/a", ""):
            vram = "unknown"
        else:
            try:
                vram = int(float(vram_raw))
            except (TypeError, ValueError):
                vram = "unknown"
        rows.append({"pid": pid, "name": name, "vram_used": vram})
    return rows


def independent_gpu_processes() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"ok": False, "error": "nvidia-smi_not_found", "source": "independent"}
    proc = subprocess.run(
        [
            binary,
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=8,
        shell=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip() or "nvidia_smi_failed", "source": "independent"}
    processes = _parse_compute_apps_csv(proc.stdout or "")
    return {"ok": True, "source": "independent_nvidia_smi", "processes": processes}


def compare_processes(tool: dict[str, Any], indep: dict[str, Any]) -> dict[str, Any]:
    if not indep.get("ok"):
        return {"overall": "UNKNOWN", "reason": indep.get("error")}
    tool_procs = tool.get("processes") or []
    indep_procs = indep.get("processes") or []
    tool_pids = {p.get("pid") for p in tool_procs if p.get("pid") is not None}
    indep_pids = {p.get("pid") for p in indep_procs if p.get("pid") is not None}
    common = tool_pids & indep_pids
    pid_match_rate = len(common) / max(len(tool_pids | indep_pids), 1)
    tool_unknown_vram = sum(1 for p in tool_procs if p.get("vram_used") == "unknown")
    indep_unknown_vram = sum(1 for p in indep_procs if p.get("vram_used") == "unknown")
    overall = "PASS"
    if pid_match_rate < 0.8 and tool.get("ok") and indep.get("ok"):
        overall = "PARTIAL"
    if not tool.get("ok") and indep.get("ok"):
        overall = "MISMATCH"
    return {
        "overall": overall,
        "tool_process_count": len(tool_procs),
        "independent_process_count": len(indep_procs),
        "common_pid_count": len(common),
        "pid_match_rate": round(pid_match_rate, 3),
        "tool_vram_unknown_count": tool_unknown_vram,
        "independent_vram_unknown_count": indep_unknown_vram,
        "vram_observation_validity": "PARTIAL",
        "note": "same-run sequential snapshot; VRAM per-process often unknown; pid set may differ by timing",
        "sample_common_pids": sorted(common)[:5],
    }


def main() -> int:
    from tools.system.gpu.gpu_processes import get_gpu_processes
    from validator.catalog_draft import generate_catalog_draft
    from validator.validate import validate_tool_spec_file

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    validation = validate_tool_spec_file(SPEC_PATH)
    catalog_draft = generate_catalog_draft(
        spec,
        spec_ref="docs/ai_tool/tool_creation/specs/get_gpu_processes_legacy_migrated.json",
    )
    catalog_draft["migration_run"] = RUN_ID
    catalog_draft["_draft_meta"]["production_catalog_modified"] = False

    tool_out = get_gpu_processes()
    indep = independent_gpu_processes()
    comparison = compare_processes(tool_out, indep)

    registry = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    reg = next(t for t in registry["tools"] if t["name"] == "get_gpu_processes")

    registry_match = {
        "verdict": "PARTIAL_MATCH",
        "matches": {
            "name": reg["name"] == spec["name"],
            "module": reg["module"] == spec["provider_specific"]["module"],
            "function": reg["function"] == spec["provider_specific"]["function"],
            "observation_source": reg.get("observation_source") == "real",
            "visibility": reg.get("visibility") == "agent",
            "input": reg.get("input") == {},
        },
        "registry_only": ["category", "subcategory", "keywords", "risk"],
        "spec_only": ["output_schema", "output_fields", "unknown_semantics", "not_provided_fields"],
    }

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/tool_creation/test_get_gpu_processes_migration.py",
        "tests/test_gpu_real_observation.py::GpuRealObservationTests::test_processes_not_fixed_ollama_python",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)

    inputs = {
        "experiment": "get_gpu_processes_legacy_migration_phase1",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip(),
        "spec_path": str(SPEC_PATH.relative_to(_REPO)),
        "baseline": "working_tree_gpu_processes.py",
        "constraints": {"implementation_changed": False, "registry_changed": False, "agent_changed": False},
    }
    evaluation = {
        "success_criteria_met": validation.verdict == "ACCEPT" and proc.returncode == 0,
        "spec_validation": validation.verdict,
        "registry_alignment": registry_match["verdict"],
        "observation_validity": "REAL (process list); PARTIAL (VRAM per-process)",
        "comparison_overall": comparison.get("overall"),
        "compatibility": "COMPATIBLE_DOCUMENTATION_ONLY",
        "repair_classification": spec.get("repair_classification"),
        "human_review": "NOT_REQUIRED",
        "recommended_action": "REPAIR",
        "pytest_passed": proc.returncode == 0,
        "stop": False,
    }

    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "outputs.json").write_text(
        json.dumps({"tool_output": tool_out, "independent": indep, "validation": validation.to_dict()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "registry_match.json").write_text(json.dumps(registry_match, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "catalog_draft.json").write_text(json.dumps(catalog_draft, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "test_result.json").write_text(
        json.dumps({"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    append_audit(
        {"event": "get_gpu_processes_migration_phase1", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# get_gpu_processes Migration — Phase 1 Run",
                "",
                f"- spec validation: **{validation.verdict}**",
                f"- registry: **{registry_match['verdict']}**",
                f"- process comparison: **{comparison.get('overall')}**",
                f"- pytest: **{'passed' if proc.returncode == 0 else 'FAILED'}**",
                f"- human review: **NOT_REQUIRED** (this phase)",
                "",
                "See `docs/ai_tool/tool_creation/GET_GPU_PROCESSES_MIGRATION.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
