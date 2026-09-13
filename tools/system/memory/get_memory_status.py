"""Windows CIM から物理メモリを実測する Tool。固定値フォールバック禁止。"""

from __future__ import annotations

import json
import platform
import subprocess

UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

_CIM_QUERY = (
    "Get-CimInstance Win32_OperatingSystem | "
    "Select-Object TotalVisibleMemorySize,FreePhysicalMemory | "
    "ConvertTo-Json -Compress"
)


def _safe_int(value: object) -> int | str:
    if value is None or value == "":
        return UNKNOWN
    try:
        return int(value)
    except (TypeError, ValueError):
        return UNKNOWN


def _failure(*, status: str, error: str) -> dict:
    return {
        "total_mb": UNKNOWN,
        "used_mb": UNKNOWN,
        "free_mb": UNKNOWN,
        "used_percent": UNKNOWN,
        "ok": False,
        "status": status,
        "error": error,
        "observation_source": "real",
        "source": "win32_operating_system_cim",
    }


def _kb_to_mb(kb: int) -> int:
    return kb // 1024


def get_memory_status() -> dict:
    """
    Win32_OperatingSystem CIM から物理メモリ total / used / free / percent を実測する。
    非 Windows は unavailable。架空の容量は返さない。
    """
    if platform.system().lower() != "windows":
        return _failure(status=UNAVAILABLE, error="non_windows")

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _CIM_QUERY],
            capture_output=True,
            text=True,
            timeout=12,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return _failure(status="error", error="cim_timeout")
    except OSError as exc:
        return _failure(status="error", error=f"{type(exc).__name__}:{exc}")

    if completed.returncode != 0:
        return _failure(
            status="error",
            error=(completed.stderr or "").strip() or "cim_failed",
        )

    raw = (completed.stdout or "").strip()
    if not raw:
        return _failure(status="error", error="cim_empty")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _failure(status="error", error="cim_json_parse_failed")

    if isinstance(payload, list):
        row = payload[0] if payload else {}
    elif isinstance(payload, dict):
        row = payload
    else:
        return _failure(status="error", error="cim_unexpected_shape")

    total_kb = _safe_int(row.get("TotalVisibleMemorySize"))
    free_kb = _safe_int(row.get("FreePhysicalMemory"))
    if not isinstance(total_kb, int) or not isinstance(free_kb, int):
        return _failure(status="error", error="cim_missing_memory_fields")
    if total_kb <= 0:
        return _failure(status="error", error="cim_total_memory_invalid")
    if free_kb < 0:
        return _failure(status="error", error="cim_free_memory_invalid")
    if free_kb > total_kb:
        return _failure(status="error", error="cim_free_exceeds_total")

    used_kb = total_kb - free_kb
    return {
        "total_mb": _kb_to_mb(total_kb),
        "used_mb": _kb_to_mb(used_kb),
        "free_mb": _kb_to_mb(free_kb),
        "used_percent": int(round(used_kb * 100 / total_kb)),
        "ok": True,
        "status": "ok",
        "error": None,
        "observation_source": "real",
        "source": "win32_operating_system_cim",
    }
