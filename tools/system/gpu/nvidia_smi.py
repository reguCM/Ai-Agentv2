"""
共有 nvidia-smi 観測（固定値フォールバック禁止）。

GPU Tool と D-1a resource_probe が同じ取得経路を使う。
欠測は unknown / unavailable / error。実測失敗時に架空 GPU 値を返さない。
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _safe_float(value: Any) -> Any:
    try:
        if value is None or value in (UNKNOWN, UNAVAILABLE, ""):
            return UNKNOWN
        text = str(value).strip()
        if not text or text.lower() in ("n/a", "[n/a]", "nan"):
            return UNKNOWN
        return float(text)
    except (TypeError, ValueError):
        return UNKNOWN


def _safe_int(value: Any) -> Any:
    number = _safe_float(value)
    if not isinstance(number, float):
        return UNKNOWN
    return int(number)


def nvidia_smi_path() -> str | None:
    return shutil.which("nvidia-smi")


def _run_nvidia_smi_query(
    binary: str,
    query: str,
    *,
    timeout: float = 8.0,
    compute_apps: bool = False,
) -> dict[str, Any]:
    if compute_apps:
        argv = [
            binary,
            f"--query-compute-apps={query}",
            "--format=csv,noheader,nounits",
        ]
    else:
        argv = [
            binary,
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "nvidia_smi_timeout",
            "status": "error",
            "rows": [],
            "source": "nvidia-smi",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "status": "error",
            "rows": [],
            "source": "nvidia-smi",
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": (completed.stderr or "").strip() or "nvidia_smi_failed",
            "status": "error",
            "rows": [],
            "source": "nvidia-smi",
        }
    rows = []
    for line in (completed.stdout or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append([p.strip() for p in line.split(",")])
    return {
        "ok": True,
        "error": None,
        "status": "ok",
        "rows": rows,
        "source": "nvidia-smi",
    }


def query_gpu_status() -> dict[str, Any]:
    """
    GPU 名 / temperature / utilization / vram_used / vram_total を実測。
    失敗時は固定値へフォールバックしない。
    """
    binary = nvidia_smi_path()
    if not binary:
        return {
            "ok": False,
            "status": UNAVAILABLE,
            "error": "nvidia-smi_not_found",
            "gpu": UNKNOWN,
            "temperature": UNKNOWN,
            "utilization": UNKNOWN,
            "vram_used": UNKNOWN,
            "vram_total": UNKNOWN,
            "observation_source": "real",
            "source": "none",
        }

    result = _run_nvidia_smi_query(
        binary,
        "name,temperature.gpu,utilization.gpu,memory.used,memory.total",
    )
    if not result["ok"] or not result["rows"]:
        return {
            "ok": False,
            "status": result.get("status") or "error",
            "error": result.get("error") or "nvidia_smi_empty",
            "gpu": UNKNOWN,
            "temperature": UNKNOWN,
            "utilization": UNKNOWN,
            "vram_used": UNKNOWN,
            "vram_total": UNKNOWN,
            "observation_source": "real",
            "source": "nvidia-smi",
        }

    parts = result["rows"][0]
    name = parts[0] if len(parts) > 0 and parts[0] else UNKNOWN
    temperature = _safe_float(parts[1] if len(parts) > 1 else None)
    utilization = _safe_float(parts[2] if len(parts) > 2 else None)
    vram_used = _safe_int(parts[3] if len(parts) > 3 else None)
    vram_total = _safe_int(parts[4] if len(parts) > 4 else None)

    return {
        "ok": True,
        "status": "ok",
        "error": None,
        "gpu": name,
        "temperature": temperature,
        "utilization": utilization,
        "vram_used": vram_used,
        "vram_total": vram_total,
        "observation_source": "real",
        "source": "nvidia-smi",
    }


def query_gpu_processes() -> dict[str, Any]:
    """
    GPU 使用中プロセスを実測。
    空リストは「プロセスなし」(ok)。固定の ollama/python は返さない。
    """
    binary = nvidia_smi_path()
    if not binary:
        return {
            "ok": False,
            "status": UNAVAILABLE,
            "error": "nvidia-smi_not_found",
            "processes": [],
            "observation_source": "real",
            "source": "none",
        }

    result = _run_nvidia_smi_query(
        binary,
        "pid,process_name,used_gpu_memory",
        compute_apps=True,
    )
    if not result["ok"]:
        return {
            "ok": False,
            "status": result.get("status") or "error",
            "error": result.get("error"),
            "processes": [],
            "observation_source": "real",
            "source": "nvidia-smi",
        }

    processes = []
    for parts in result["rows"]:
        pid = _safe_int(parts[0] if len(parts) > 0 else None)
        name = parts[1] if len(parts) > 1 and parts[1] else UNKNOWN
        vram = _safe_int(parts[2] if len(parts) > 2 else None)
        processes.append(
            {
                "pid": pid,
                "name": name,
                "vram_used": vram,
            }
        )

    return {
        "ok": True,
        "status": "ok",
        "error": None,
        "processes": processes,
        "observation_source": "real",
        "source": "nvidia-smi",
    }


def probe_gpu_memory_and_util() -> dict[str, Any]:
    """D-1a resource_probe 向け: bytes / utilization。固定値なし。"""
    binary = nvidia_smi_path()
    if not binary:
        return {
            "gpu_memory_free_bytes": UNKNOWN,
            "gpu_memory_used_bytes": UNKNOWN,
            "gpu_utilization": UNKNOWN,
            "gpu_source": "none",
            "gpu_error": "nvidia-smi_not_found",
        }
    result = _run_nvidia_smi_query(
        binary, "memory.free,memory.used,utilization.gpu"
    )
    if not result["ok"] or not result["rows"]:
        return {
            "gpu_memory_free_bytes": UNKNOWN,
            "gpu_memory_used_bytes": UNKNOWN,
            "gpu_utilization": UNKNOWN,
            "gpu_source": "nvidia-smi",
            "gpu_error": result.get("error") or "nvidia_smi_empty",
        }
    parts = result["rows"][0]
    free_mib = _safe_float(parts[0] if len(parts) > 0 else None)
    used_mib = _safe_float(parts[1] if len(parts) > 1 else None)
    util = _safe_float(parts[2] if len(parts) > 2 else None)
    return {
        "gpu_memory_free_bytes": int(free_mib * 1024 * 1024)
        if isinstance(free_mib, float)
        else UNKNOWN,
        "gpu_memory_used_bytes": int(used_mib * 1024 * 1024)
        if isinstance(used_mib, float)
        else UNKNOWN,
        "gpu_utilization": util,
        "gpu_source": "nvidia-smi",
    }
