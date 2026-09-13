#!/usr/bin/env python3
"""get_gpu_status Legacy → Current Migration Phase 1 — isolated run (read-only)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TOOL_CREATION = _REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_get_gpu_status_migration"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
SPEC_PATH = TOOL_CREATION / "specs" / "get_gpu_status_legacy_migrated.json"


def _compare_field(tool_val, indep_val, *, tol=15.0):
    if tool_val is None or indep_val is None:
        return "UNKNOWN"
    if isinstance(tool_val, (int, float)) and isinstance(indep_val, (int, float)):
        return "PASS" if abs(float(tool_val) - float(indep_val)) <= tol else "MISMATCH"
    return "PASS" if str(tool_val).strip() == str(indep_val).strip() else "MISMATCH"


def main() -> int:
    from tools.system.gpu.gpu_status import get_gpu_status
    from validator.catalog_draft import generate_catalog_draft
    from validator.validate import validate_tool_spec_file

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    validation = validate_tool_spec_file(SPEC_PATH)
    catalog_draft = generate_catalog_draft(
        spec,
        spec_ref="docs/ai_tool/tool_creation/specs/get_gpu_status_legacy_migrated.json",
    )
    catalog_draft["migration_run"] = RUN_ID
    catalog_draft["_draft_meta"]["production_catalog_modified"] = False

    # Same-moment comparison
    tool_out = get_gpu_status()
    binary = shutil.which("nvidia-smi")
    indep = {"ok": False, "error": "nvidia-smi_not_found"}
    if binary:
        proc = subprocess.run(
            [
                binary,
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = [p.strip() for p in proc.stdout.strip().split(",")]
            indep = {
                "ok": True,
                "gpu": parts[0] if len(parts) > 0 else None,
                "temperature": float(parts[1]) if len(parts) > 1 else None,
                "utilization": float(parts[2]) if len(parts) > 2 else None,
                "vram_used": int(float(parts[3])) if len(parts) > 3 else None,
                "vram_total": int(float(parts[4])) if len(parts) > 4 else None,
            }

    comparison = {}
    if indep.get("ok"):
        fields = {}
        for key in ("gpu", "temperature", "utilization", "vram_used", "vram_total"):
            tol = 15.0 if key in ("utilization", "vram_used") else 5.0
            fields[key] = {
                "tool": tool_out.get(key),
                "independent": indep.get(key),
                "comparison": _compare_field(tool_out.get(key), indep.get(key), tol=tol),
            }
        overall = "PASS"
        if any(v["comparison"] == "MISMATCH" for v in fields.values()):
            overall = "PARTIAL"
        comparison = {"overall": overall, "fields": fields, "note": "same-run sequential snapshot"}
    else:
        comparison = {"overall": "UNKNOWN", "reason": indep.get("error")}

    registry = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    reg = next(t for t in registry["tools"] if t["name"] == "get_gpu_status")

    registry_match = {
        "verdict": "PARTIAL_MATCH",
        "matches": {
            "name": reg["name"] == spec["name"],
            "module": reg["module"] == spec["provider_specific"]["module"],
            "function": reg["function"] == spec["provider_specific"]["function"],
            "observation_source": reg.get("observation_source") == "real",
            "visibility": reg.get("visibility") == "agent",
        },
        "registry_only": ["category", "subcategory", "keywords", "risk"],
        "spec_only": ["output_schema", "output_fields", "contract", "version"],
    }

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/tool_creation/test_get_gpu_status_migration.py",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)

    inputs = {
        "experiment": "get_gpu_status_legacy_migration_phase1",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip(),
        "spec_path": str(SPEC_PATH.relative_to(_REPO)),
        "constraints": {"implementation_changed": False, "registry_changed": False, "agent_changed": False},
    }
    evaluation = {
        "success_criteria_met": validation.verdict == "ACCEPT" and proc.returncode == 0,
        "spec_validation": validation.verdict,
        "registry_alignment": registry_match["verdict"],
        "observation": "REAL" if tool_out.get("ok") else "UNKNOWN",
        "comparison_overall": comparison.get("overall"),
        "compatibility": "NO_CHANGE",
        "recommended_action": "KEEP",
        "pytest_passed": proc.returncode == 0,
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
        {"event": "get_gpu_status_migration_phase1", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# get_gpu_status Migration — Phase 1 Run",
                "",
                f"- spec validation: **{validation.verdict}**",
                f"- registry: **{registry_match['verdict']}**",
                f"- comparison: **{comparison.get('overall')}**",
                f"- pytest: **{'passed' if proc.returncode == 0 else 'FAILED'}**",
                "",
                "See `docs/ai_tool/tool_creation/GET_GPU_STATUS_MIGRATION.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
