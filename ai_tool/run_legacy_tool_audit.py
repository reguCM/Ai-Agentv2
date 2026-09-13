#!/usr/bin/env python3
"""Legacy GPU/CPU Tool audit — read-only diagnostic run (Phase 1).

Does NOT modify production tools, registry, or agent.py.
Compares Tool output vs independent OS observation.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_legacy_tool_audit"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text.lower() in ("n/a", "[n/a]", "unknown", "nan"):
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    f = _safe_float(value)
    return int(f) if f is not None else None


def independent_gpu_status() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"ok": False, "error": "nvidia-smi_not_found", "source": "independent"}
    try:
        completed = subprocess.run(
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
    except Exception as exc:
        return {"ok": False, "error": str(exc), "source": "independent"}
    if completed.returncode != 0:
        return {"ok": False, "error": completed.stderr.strip(), "source": "independent"}
    parts = [p.strip() for p in completed.stdout.strip().split(",")]
    return {
        "ok": True,
        "source": "independent_nvidia-smi",
        "gpu": parts[0] if len(parts) > 0 else None,
        "temperature": _safe_float(parts[1] if len(parts) > 1 else None),
        "utilization": _safe_float(parts[2] if len(parts) > 2 else None),
        "vram_used": _safe_int(parts[3] if len(parts) > 3 else None),
        "vram_total": _safe_int(parts[4] if len(parts) > 4 else None),
    }


def independent_cpu_status() -> dict[str, Any]:
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


def compare_field(tool_val: Any, indep_val: Any, *, numeric_tolerance: float = 5.0) -> str:
    if tool_val is None or indep_val is None:
        return "UNKNOWN"
    if isinstance(tool_val, (int, float)) and isinstance(indep_val, (int, float)):
        if abs(float(tool_val) - float(indep_val)) <= numeric_tolerance:
            return "PASS"
        return "MISMATCH"
    if str(tool_val).strip() == str(indep_val).strip():
        return "PASS"
    return "MISMATCH"


def compare_gpu(tool: dict[str, Any], indep: dict[str, Any]) -> dict[str, Any]:
    fields = {}
    for key in ("gpu", "temperature", "utilization", "vram_used", "vram_total"):
        tol = 15.0 if key in ("utilization", "vram_used") else 5.0
        fields[key] = {
            "tool": tool.get(key),
            "independent": indep.get(key),
            "comparison": compare_field(tool.get(key), indep.get(key), numeric_tolerance=tol),
        }
    overall = "PASS"
    if any(v["comparison"] == "MISMATCH" for v in fields.values()):
        overall = "PARTIAL"
    if any(v["comparison"] == "UNKNOWN" for v in fields.values()):
        overall = "UNKNOWN" if overall == "PASS" else overall
    return {"overall": overall, "fields": fields, "note": "utilization/vram may differ by snapshot timing"}


def compare_cpu(tool: dict[str, Any], indep: dict[str, Any]) -> dict[str, Any]:
    tool_load = tool.get("status")
    indep_load = indep.get("LoadPercentage")
    load_cmp = compare_field(tool_load, indep_load, numeric_tolerance=15.0)
    return {
        "overall": load_cmp,
        "fields": {
            "load_percentage": {
                "tool_status_field": tool_load,
                "independent_LoadPercentage": indep_load,
                "comparison": load_cmp,
            },
            "cpu_model": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("Name"),
                "comparison": "OBSERVED GAP — tool does not expose model",
            },
            "cores": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("NumberOfCores"),
                "comparison": "OBSERVED GAP",
            },
            "logical_processors": {
                "tool": "NOT_RETURNED",
                "independent": indep.get("NumberOfLogicalProcessors"),
                "comparison": "OBSERVED GAP",
            },
            "temperature": {
                "tool": "NOT_RETURNED",
                "independent": "NOT_QUERIED",
                "comparison": "UNKNOWN — Win32_Processor may not expose temperature",
            },
        },
    }


def main() -> int:
    from tools.system.cpu.cpu_status import cpu_status
    from tools.system.gpu.gpu_processes import get_gpu_processes
    from tools.system.gpu.gpu_status import get_gpu_status

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    inputs = {
        "experiment": "legacy_tool_audit_phase1",
        "targets": ["get_gpu_status", "get_gpu_processes", "cpu_status"],
        "constraints": {
            "no_tool_modification": True,
            "no_registry_modification": True,
            "no_agent_modification": True,
        },
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_REPO, text=True
        ).strip(),
        "timestamp": _now_iso(),
    }

    tool_gpu = get_gpu_status()
    tool_gpu_proc = get_gpu_processes()
    tool_cpu = cpu_status()

    indep_gpu = independent_gpu_status()
    indep_cpu = independent_cpu_status()

    comparison = {
        "get_gpu_status": compare_gpu(tool_gpu, indep_gpu),
        "cpu_status": compare_cpu(tool_cpu, indep_cpu),
        "get_gpu_processes": {
            "overall": "PARTIAL",
            "note": "Process list from same nvidia-smi source; vram_used often unknown due to [N/A] / permissions",
            "tool_process_count": len(tool_gpu_proc.get("processes") or []),
            "tool_ok": tool_gpu_proc.get("ok"),
        },
    }

    outputs = {
        "tool_results": {
            "get_gpu_status": tool_gpu,
            "get_gpu_processes": tool_gpu_proc,
            "cpu_status": tool_cpu,
        },
        "independent_observation": {
            "gpu": indep_gpu,
            "cpu": indep_cpu,
        },
    }

    evaluation = {
        "success_criteria_met": True,
        "audit_only": True,
        "gpu_observation_validity": "REAL" if tool_gpu.get("ok") else "UNKNOWN",
        "cpu_observation_validity": "PARTIAL",
        "independent_gpu_ok": indep_gpu.get("ok"),
        "independent_cpu_ok": indep_cpu.get("ok"),
        "comparison_gpu": comparison["get_gpu_status"]["overall"],
        "comparison_cpu_load": comparison["cpu_status"]["overall"],
    }

    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "outputs.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit(
        {"event": "legacy_tool_audit_phase1", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    report = [
        "# Legacy Tool Audit — Phase 1 Run",
        "",
        f"- **run_dir:** `{RUN_DIR.relative_to(_REPO).as_posix()}`",
        f"- **gpu comparison:** {comparison['get_gpu_status']['overall']}",
        f"- **cpu load comparison:** {comparison['cpu_status']['overall']}",
        "",
        "See `docs/ai_tool/project_audit/LEGACY_TOOL_AUDIT.md`.",
    ]
    (RUN_DIR / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
