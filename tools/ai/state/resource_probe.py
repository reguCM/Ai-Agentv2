"""
Phase D-1a: 環境リソース実測（閾値判定なし）。

取得不能は unknown。disk 10% 等の固定閾値で AUTO/BLOCK しない。
resource_safety は常に unknown（未評価）を維持する。
"""

from __future__ import annotations

import os
import shutil
from typing import Any

UNKNOWN = "unknown"


def _safe_int(value: Any) -> Any:
    try:
        if value is None or value is UNKNOWN:
            return UNKNOWN
        return int(value)
    except (TypeError, ValueError):
        return UNKNOWN


def _safe_float(value: Any) -> Any:
    try:
        if value is None or value is UNKNOWN:
            return UNKNOWN
        return float(value)
    except (TypeError, ValueError):
        return UNKNOWN


def _probe_disk(path: str | None = None) -> dict[str, Any]:
    target = path or os.getcwd()
    try:
        usage = shutil.disk_usage(target)
        total = int(usage.total)
        free = int(usage.free)
        ratio = (free / total) if total else UNKNOWN
        return {
            "disk_path": target,
            "disk_total_bytes": total,
            "disk_free_bytes": free,
            "disk_free_ratio": ratio,
        }
    except Exception as exc:
        return {
            "disk_path": target,
            "disk_total_bytes": UNKNOWN,
            "disk_free_bytes": UNKNOWN,
            "disk_free_ratio": UNKNOWN,
            "disk_error": f"{type(exc).__name__}:{exc}",
        }


def _probe_memory() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        vm = psutil.virtual_memory()
        return {
            "memory_available_bytes": int(vm.available),
            "memory_total_bytes": int(vm.total),
            "memory_source": "psutil",
        }
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return {
                    "memory_available_bytes": int(stat.ullAvailPhys),
                    "memory_total_bytes": int(stat.ullTotalPhys),
                    "memory_source": "GlobalMemoryStatusEx",
                }
        except Exception as exc:
            return {
                "memory_available_bytes": UNKNOWN,
                "memory_total_bytes": UNKNOWN,
                "memory_source": "none",
                "memory_error": f"{type(exc).__name__}:{exc}",
            }
    return {
        "memory_available_bytes": UNKNOWN,
        "memory_total_bytes": UNKNOWN,
        "memory_source": "none",
    }


def _probe_cpu() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        # interval=None は前回との差。初回は None になり得るので短時間サンプリング
        load = psutil.cpu_percent(interval=0.05)
        return {
            "cpu_load": float(load),
            "cpu_count": int(psutil.cpu_count() or 0) or UNKNOWN,
            "cpu_source": "psutil",
        }
    except Exception:
        pass
    try:
        loadavg = os.getloadavg()  # type: ignore[attr-defined]
        return {
            "cpu_load": float(loadavg[0]),
            "cpu_loadavg": list(loadavg),
            "cpu_source": "getloadavg",
        }
    except Exception:
        return {
            "cpu_load": UNKNOWN,
            "cpu_count": UNKNOWN,
            "cpu_source": "none",
        }


def _probe_gpu() -> dict[str, Any]:
    from tools.system.gpu.nvidia_smi import probe_gpu_memory_and_util

    return probe_gpu_memory_and_util()


def _probe_processes() -> dict[str, Any]:
    try:
        import psutil  # type: ignore

        count = len(psutil.pids())
        return {
            "active_processes": int(count),
            "process_source": "psutil",
        }
    except Exception:
        return {
            "active_processes": UNKNOWN,
            "process_source": "none",
        }


def probe_environment_resources(*, disk_path: str | None = None) -> dict[str, Any]:
    """
    環境リソースを機械観測する。閾値判定・安全結論は行わない。
    """
    disk = _probe_disk(disk_path)
    memory = _probe_memory()
    cpu = _probe_cpu()
    gpu = _probe_gpu()
    procs = _probe_processes()
    codes = [
        "resource_probe_phase_d1a",
        "no_disk_10_percent_rule",
        "no_fixed_resource_thresholds",
        "resource_unknown_not_treated_as_safe",
        "observation_only_not_policy_decision",
    ]
    return {
        "phase": "kss-phase-d1a",
        "disk_free_bytes": disk.get("disk_free_bytes", UNKNOWN),
        "disk_free_ratio": disk.get("disk_free_ratio", UNKNOWN),
        "disk_total_bytes": disk.get("disk_total_bytes", UNKNOWN),
        "disk_path": disk.get("disk_path"),
        "memory_available_bytes": memory.get("memory_available_bytes", UNKNOWN),
        "memory_total_bytes": memory.get("memory_total_bytes", UNKNOWN),
        "gpu_memory_free_bytes": gpu.get("gpu_memory_free_bytes", UNKNOWN),
        "gpu_memory_used_bytes": gpu.get("gpu_memory_used_bytes", UNKNOWN),
        "cpu_load": cpu.get("cpu_load", UNKNOWN),
        "gpu_utilization": gpu.get("gpu_utilization", UNKNOWN),
        "active_processes": procs.get("active_processes", UNKNOWN),
        "resource_limits": UNKNOWN,
        "source": "local_probe",
        "probe_details": {
            "disk": disk,
            "memory": memory,
            "cpu": cpu,
            "gpu": gpu,
            "processes": procs,
        },
        "rationale_codes": codes,
        "thresholds_applied": False,
    }


def diff_resource_snapshots(before: dict | None, after: dict | None) -> dict[str, Any]:
    """実行前後差分（観測用）。安全判定には使わない。"""
    before = before or {}
    after = after or {}

    def _delta(key: str) -> Any:
        b = before.get(key)
        a = after.get(key)
        if not isinstance(b, (int, float)) or not isinstance(a, (int, float)):
            return UNKNOWN
        return a - b

    return {
        "disk_free_bytes_delta": _delta("disk_free_bytes"),
        "memory_available_bytes_delta": _delta("memory_available_bytes"),
        "gpu_memory_free_bytes_delta": _delta("gpu_memory_free_bytes"),
        "gpu_memory_used_bytes_delta": _delta("gpu_memory_used_bytes"),
        "cpu_load_delta": _delta("cpu_load"),
        "gpu_utilization_delta": _delta("gpu_utilization"),
        "active_processes_delta": _delta("active_processes"),
        "note": "差分は観測専用。AUTO/BLOCK 条件にはしません。",
        "rationale_codes": ["resource_delta_observation_only"],
    }


def build_resource_assessment_from_probe(
    resources: dict | None,
    *,
    resource_impact: dict | None = None,
    execution_runtime: dict | None = None,
) -> dict[str, Any]:
    """Policy 用 resource_assessment。resource_safety は unknown 固定。"""
    resources = resources or probe_environment_resources()
    return {
        "environment_resources": resources,
        "resource_impact": resource_impact
        or {
            "disk_growth": UNKNOWN,
            "memory_consumption": UNKNOWN,
            "gpu_memory_consumption": UNKNOWN,
            "cpu_consumption": UNKNOWN,
            "execution_duration": UNKNOWN,
            "unbounded_execution": UNKNOWN,
            "rationale_codes": ["resource_impact_filled_after_execution_if_any"],
        },
        "execution_runtime": execution_runtime
        or {
            "duration_estimate": UNKNOWN,
            "termination_statically_known": UNKNOWN,
            "infinite_loop_suspected": UNKNOWN,
            "stop_means_available": UNKNOWN,
            "child_process_fanout_risk": UNKNOWN,
            "rationale_codes": [
                "execution_runtime_observation_phase_d1a",
                "long_running_not_defined_as_dangerous",
            ],
        },
        "resource_safety": {
            "status": UNKNOWN,
            "rationale_codes": [
                "resource_not_evaluated_for_policy_phase_d1a",
                "resource_unknown_not_treated_as_safe",
                "no_fixed_resource_thresholds",
            ],
        },
        "not_merged_into_machine_safety": True,
        "web_content_used": False,
        "llm_final_authority": False,
        "thresholds_applied": False,
        "observation_only": True,
    }
