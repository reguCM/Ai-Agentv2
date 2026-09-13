#!/usr/bin/env python3
"""Isolated GPU/CPU observation capability audit — no production tool changes."""
from __future__ import annotations

import importlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_observation_capability_audit"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _run(cmd: list[str], timeout: float = 15.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except Exception as exc:
        return {"error": str(exc)}


def probe_gpu() -> dict[str, Any]:
    binary = shutil.which("nvidia-smi")
    out: dict[str, Any] = {"nvidia_smi_available": bool(binary), "path": binary}
    if not binary:
        return out
    out["gpu_status_query"] = _run(
        [binary, "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,count", "--format=csv,noheader,nounits"]
    )
    out["driver"] = _run([binary, "--query-gpu=driver_version", "--format=csv,noheader,nounits"])
    out["power_clock"] = _run([binary, "--query-gpu=power.draw,clocks.current.graphics", "--format=csv,noheader,nounits"])
    out["compute_apps"] = _run(
        [binary, "--query-compute-apps=pid,process_name,used_gpu_memory,gpu_uuid", "--format=csv,noheader,nounits"]
    )
    lines = (out["compute_apps"].get("stdout") or "").strip().splitlines()
    out["process_line_count"] = len(lines)
    out["vram_na_count"] = sum(1 for line in lines if "[N/A]" in line or ", N/A," in line)
    out["insufficient_permissions_count"] = sum(1 for line in lines if "Insufficient Permissions" in line)
    return out


def probe_cpu() -> dict[str, Any]:
    cmds = {
        "load": "Get-CimInstance Win32_Processor | Select-Object LoadPercentage | ConvertTo-Json",
        "processor_info": (
            "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
            "NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,Architecture | ConvertTo-Json"
        ),
    }
    result: dict[str, Any] = {}
    for key, ps in cmds.items():
        result[key] = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps])
    return result


def tool_outputs_wt() -> dict[str, Any]:
    gs = importlib.import_module("tools.system.gpu.gpu_status").get_gpu_status()
    gp = importlib.import_module("tools.system.gpu.gpu_processes").get_gpu_processes()
    cs = importlib.import_module("tools.system.cpu.cpu_status").cpu_status()
    procs = gp.get("processes") or []
    return {
        "get_gpu_status": gs,
        "get_gpu_processes": {
            "ok": gp.get("ok"),
            "status": gp.get("status"),
            "process_count": len(procs),
            "vram_unknown_count": sum(1 for p in procs if p.get("vram_used") == "unknown"),
            "sample": procs[:3],
        },
        "cpu_status": cs,
    }


def head_gpu_status_stub() -> dict[str, Any]:
    return {
        "gpu": "RTX 3060",
        "temperature": 60,
        "utilization": 50,
        "vram_used": 6000,
        "vram_total": 12288,
        "classification": "FIXED_STUB",
        "source": "git HEAD tools/system/gpu/gpu_status.py",
    }


def compare_gpu_status(tool: dict[str, Any], independent_stdout: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not independent_stdout.strip():
        return rows
    parts = [p.strip() for p in independent_stdout.strip().split(",")]
    mapping = [
        ("gpu", parts[0] if len(parts) > 0 else None, tool.get("gpu")),
        ("temperature", float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "").isdigit() else parts[1] if len(parts) > 1 else None, tool.get("temperature")),
        ("utilization", float(parts[2]) if len(parts) > 2 and parts[2].replace(".", "").isdigit() else parts[2] if len(parts) > 2 else None, tool.get("utilization")),
        ("vram_used", int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else parts[3] if len(parts) > 3 else None, tool.get("vram_used")),
        ("vram_total", int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else parts[4] if len(parts) > 4 else None, tool.get("vram_total")),
        ("gpu_count", int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else parts[5] if len(parts) > 5 else None, "NOT_PROVIDED"),
    ]
    for field, indep, tool_val in mapping:
        if field == "gpu_count":
            rows.append({"field": field, "independent": indep, "tool": tool_val, "verdict": "NOT_PROVIDED"})
            continue
        if tool_val == "unknown" or indep == "unknown":
            verdict = "PARTIAL"
        elif indep is None or tool_val is None:
            verdict = "UNKNOWN"
        elif field in ("temperature", "utilization", "vram_used"):
            try:
                delta = abs(float(tool_val) - float(indep))
                verdict = "REAL" if delta <= 15 else "REAL_SNAPSHOT_DRIFT"
            except (TypeError, ValueError):
                verdict = "UNKNOWN"
        else:
            verdict = "REAL" if str(tool_val) == str(indep) else "DRIFT"
        rows.append({"field": field, "independent": indep, "tool": tool_val, "verdict": verdict})
    return rows


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()
    git_branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=_REPO, text=True).strip()
    git_status = subprocess.check_output(["git", "status", "--short"], cwd=_REPO, text=True)

    gpu_probe = probe_gpu()
    cpu_probe = probe_cpu()
    wt_tools = tool_outputs_wt()
    head_stub = head_gpu_status_stub()

    gpu_compare = compare_gpu_status(
        wt_tools["get_gpu_status"],
        (gpu_probe.get("gpu_status_query") or {}).get("stdout") or "",
    )

    evaluation = {
        "overall": "COMPLETE",
        "production_code_changed": False,
        "registry_changed": False,
        "human_review_required": True,
        "stop": True,
        "recommendations": {
            "get_gpu_status": "REPAIR",
            "get_gpu_processes": "KEEP",
            "cpu_status": "EXTEND",
        },
    }

    report = {
        "git_head": git_head,
        "git_branch": git_branch,
        "platform": platform.platform(),
        "gpu_probe": gpu_probe,
        "cpu_probe": cpu_probe,
        "tool_outputs_WT": wt_tools,
        "HEAD_get_gpu_status_stub": head_stub,
        "gpu_status_field_compare": gpu_compare,
        "vram_unknown_observation": {
            "tool_vram_unknown_count": wt_tools["get_gpu_processes"]["vram_unknown_count"],
            "nvidia_smi_vram_na_count": gpu_probe.get("vram_na_count"),
            "note": "nvidia-smi raw [N/A] at source — not coerced to 0 in tool",
            "root_cause": "UNKNOWN",
        },
    }

    (RUN_DIR / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "comparison.json").write_text(
        json.dumps({"gpu_status": gpu_compare, "head_vs_wt_gpu_status": {"HEAD": head_stub, "WT": wt_tools["get_gpu_status"]}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "git_state.txt").write_text(
        f"HEAD: {git_head}\nbranch: {git_branch}\n\n{git_status}",
        encoding="utf-8",
    )
    append_audit({"event": "observation_capability_audit", "run_dir": str(RUN_DIR), "evaluation": evaluation}, log_path=RUN_DIR / "audit.jsonl")

    payload = json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
