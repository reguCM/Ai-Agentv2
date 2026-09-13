"""get_gpu_status / get_gpu_processes ラッパ（事実記録用）。"""
from __future__ import annotations

from typing import Any

from tools.system.gpu.gpu_processes import get_gpu_processes
from tools.system.gpu.gpu_status import get_gpu_status


def _vram_free_mib(status: dict[str, Any]) -> int | None:
    used = status.get("vram_used")
    total = status.get("vram_total")
    if isinstance(used, int) and isinstance(total, int):
        return total - used
    return None


def snapshot_gpu() -> dict[str, Any]:
    """実行前/後 GPU 状態（事実のみ）。"""
    status = get_gpu_status()
    processes = get_gpu_processes()
    proc_list = processes.get("processes") or []
    return {
        "gpu_status": status,
        "gpu_processes": processes,
        "gpu_name": status.get("gpu"),
        "vram_total_mib": status.get("vram_total"),
        "vram_used_mib": status.get("vram_used"),
        "vram_free_mib": _vram_free_mib(status),
        "gpu_utilization": status.get("utilization"),
        "gpu_temperature": status.get("temperature"),
        "processes": [
            {
                "pid": p.get("pid"),
                "name": p.get("name") or p.get("process_name"),
                "vram_mib": p.get("vram_used") or p.get("used_gpu_memory"),
            }
            for p in proc_list
            if isinstance(p, dict)
        ],
        "process_count": len(proc_list),
    }
