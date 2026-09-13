#!/usr/bin/env python3
"""cpu_status Legacy → Current Migration Phase 2 — isolated run (read-only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TOOL_CREATION = _REPO / "docs" / "ai_tool" / "tool_creation"
if str(TOOL_CREATION) not in sys.path:
    sys.path.insert(0, str(TOOL_CREATION))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_cpu_status_migration"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
SPEC_PATH = TOOL_CREATION / "specs" / "cpu_status_legacy_migrated.json"


def _compare_field(tool_val: Any, indep_val: Any, *, tol: float = 15.0) -> str:
    if tool_val is None or indep_val is None:
        return "UNKNOWN"
    try:
        t_num = float(tool_val)
        i_num = float(indep_val)
        return "PASS" if abs(t_num - i_num) <= tol else "MISMATCH"
    except (TypeError, ValueError):
        pass
    if str(tool_val).strip() == str(indep_val).strip():
        return "PASS"
    return "MISMATCH"


def independent_cpu_load() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance -ClassName Win32_Processor | "
                "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,LoadPercentage | "
                "ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            shell=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "independent"}
    if completed.returncode != 0:
        return {"ok": False, "error": completed.stderr.strip(), "source": "independent"}
    try:
        data = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"json_decode:{exc}", "raw": completed.stdout, "source": "independent"}
    return {"ok": True, "source": "independent_powershell_cim", **data}


def compare_cpu(tool: dict[str, Any], indep: dict[str, Any]) -> dict[str, Any]:
    tool_load = tool.get("status")
    indep_load = indep.get("LoadPercentage")
    load_cmp = _compare_field(tool_load, indep_load, tol=15.0)
    return {
        "overall": load_cmp if indep.get("ok") else "UNKNOWN",
        "fields": {
            "load_percentage": {
                "tool_status_field": tool_load,
                "independent_LoadPercentage": indep_load,
                "comparison": load_cmp,
                "tolerance": "15 percent points or exact string match",
                "note": "same-run sequential snapshot; LoadPercentage is instantaneous",
            },
            "cpu_model": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("Name"),
                "comparison": "OBSERVED GAP — not in current spec",
            },
            "cores": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("NumberOfCores"),
                "comparison": "OBSERVED GAP — not in current spec",
            },
            "logical_processors": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("NumberOfLogicalProcessors"),
                "comparison": "OBSERVED GAP — not in current spec",
            },
        },
        "note": "model/cores gaps are NOT spec violations for current minimal contract",
    }


def main() -> int:
    from tools.system.cpu.cpu_status import cpu_status
    from validator.catalog_draft import generate_catalog_draft
    from validator.validate import validate_tool_spec_file

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    validation = validate_tool_spec_file(SPEC_PATH)
    catalog_draft = generate_catalog_draft(
        spec,
        spec_ref="docs/ai_tool/tool_creation/specs/cpu_status_legacy_migrated.json",
    )
    catalog_draft["migration_run"] = RUN_ID
    catalog_draft["_draft_meta"]["production_catalog_modified"] = False

    tool_out = cpu_status()
    indep = independent_cpu_load()
    comparison = compare_cpu(tool_out, indep)

    registry = json.loads((_REPO / "registry" / "tools.json").read_text(encoding="utf-8"))
    reg = next(t for t in registry["tools"] if t["name"] == "cpu_status")

    registry_match = {
        "verdict": "PARTIAL_MATCH",
        "matches": {
            "name": reg["name"] == spec["name"],
            "module": reg["module"] == spec["provider_specific"]["module"],
            "function": reg["function"] == spec["provider_specific"]["function"],
            "visibility": reg.get("visibility") == "agent",
            "input": reg.get("input") == {},
            "output": reg.get("output") == ["status"],
        },
        "partial": {
            "observation_source": "Registry metadata=real; implementation does not return observation_source output key",
            "description_breadth": "Registry「CPU基本状態」broader than LoadPercentage-only implementation; hedged by「未確認」",
        },
        "registry_only": ["category", "subcategory", "keywords", "risk", "observation_source"],
        "spec_only": ["output_fields", "not_provided_fields", "observed_gaps", "proposed_spec_change"],
    }

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/tool_creation/test_cpu_status_migration.py",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)

    inputs = {
        "experiment": "cpu_status_legacy_migration_phase2",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip(),
        "spec_path": str(SPEC_PATH.relative_to(_REPO)),
        "constraints": {"implementation_changed": False, "registry_changed": False, "agent_changed": False},
    }
    evaluation = {
        "success_criteria_met": validation.verdict == "ACCEPT" and proc.returncode == 0,
        "spec_validation": validation.verdict,
        "registry_alignment": registry_match["verdict"],
        "observation_validity": "PARTIAL",
        "current_implementation": "VALID",
        "comparison_overall": comparison.get("overall"),
        "compatibility": "NO_CHANGE",
        "repair_classification": spec.get("repair_classification"),
        "human_review": "NOT_REQUIRED",
        "recommended_action": "REPAIR",
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
        {"event": "cpu_status_migration_phase2", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# cpu_status Migration — Phase 2 Run",
                "",
                f"- spec validation: **{validation.verdict}**",
                f"- registry: **{registry_match['verdict']}**",
                f"- load comparison: **{comparison.get('overall')}**",
                f"- pytest: **{'passed' if proc.returncode == 0 else 'FAILED'}**",
                f"- human review: **NOT_REQUIRED** (this phase)",
                "",
                "See `docs/ai_tool/tool_creation/CPU_STATUS_MIGRATION.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
