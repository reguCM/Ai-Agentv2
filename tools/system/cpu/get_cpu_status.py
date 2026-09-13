"""Windows CIM から CPU 一般メトリクスを実測する Tool（Legacy cpu_status とは別 ID）。"""

from __future__ import annotations

import json
import platform
import subprocess

UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

_CIM_QUERY = (
    "Get-CimInstance Win32_Processor | "
    "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,"
    "MaxClockSpeed,CurrentClockSpeed,Architecture,LoadPercentage | "
    "ConvertTo-Json -Compress"
)


def _safe_int(value: object) -> int | str:
    if value is None or value == "":
        return UNKNOWN
    try:
        return int(value)
    except (TypeError, ValueError):
        return UNKNOWN


def _safe_str(value: object) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).strip()
    return text if text else UNKNOWN


def _failure(
    *,
    status: str,
    error: str,
) -> dict:
    return {
        "model": UNKNOWN,
        "physical_cores": UNKNOWN,
        "logical_processors": UNKNOWN,
        "load_percentage": UNKNOWN,
        "max_clock_mhz": UNKNOWN,
        "current_clock_mhz": UNKNOWN,
        "architecture": UNKNOWN,
        "ok": False,
        "status": status,
        "error": error,
        "observation_source": "real",
        "source": "win32_processor_cim",
    }


def get_cpu_status() -> dict:
    """
    Win32_Processor CIM から CPU model / cores / threads / load / clock を実測する。
    温度は UNSUPPORTED（別 Tool 候補）。非 Windows は unavailable。
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

    return {
        "model": _safe_str(row.get("Name")),
        "physical_cores": _safe_int(row.get("NumberOfCores")),
        "logical_processors": _safe_int(row.get("NumberOfLogicalProcessors")),
        "load_percentage": _safe_int(row.get("LoadPercentage")),
        "max_clock_mhz": _safe_int(row.get("MaxClockSpeed")),
        "current_clock_mhz": _safe_int(row.get("CurrentClockSpeed")),
        "architecture": _safe_int(row.get("Architecture")),
        "ok": True,
        "status": "ok",
        "error": None,
        "observation_source": "real",
        "source": "win32_processor_cim",
    }
