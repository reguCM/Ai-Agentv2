"""
Phase B: ホスト環境の構造化（推測しない。欠落は unknown）。
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from typing import Any

UNKNOWN = "unknown"

OS_FAMILY_WINDOWS = "windows"
OS_FAMILY_LINUX = "linux"
OS_FAMILY_DARWIN = "darwin"
OS_FAMILY_UNKNOWN = UNKNOWN


def normalize_os_family(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text or text == UNKNOWN:
        return OS_FAMILY_UNKNOWN
    if "win" in text:
        return OS_FAMILY_WINDOWS
    if "linux" in text or text in ("ubuntu", "debian", "fedora", "centos"):
        return OS_FAMILY_LINUX
    if "darwin" in text or "mac" in text:
        return OS_FAMILY_DARWIN
    return OS_FAMILY_UNKNOWN


def _privilege_level() -> str:
    """取得できない場合は unknown。推測で admin にしない。"""
    try:
        if os.name == "nt":
            import ctypes

            try:
                if bool(ctypes.windll.shell32.IsUserAnAdmin()):
                    return "admin"
                return "user"
            except Exception:
                return UNKNOWN
        if hasattr(os, "geteuid"):
            return "admin" if os.geteuid() == 0 else "user"
    except Exception:
        return UNKNOWN
    return UNKNOWN


def _detect_shell() -> str:
    shell = os.environ.get("ComSpec") or os.environ.get("SHELL") or ""
    shell = str(shell).strip()
    if not shell:
        return UNKNOWN
    base = os.path.basename(shell).lower()
    if "powershell" in base or base in ("pwsh.exe", "pwsh"):
        return "powershell"
    if base in ("cmd.exe", "cmd"):
        return "cmd"
    if "bash" in base:
        return "bash"
    if "zsh" in base:
        return "zsh"
    return base or UNKNOWN


def build_environment_context(
    inventory: dict | None = None,
    verified_environment: dict | None = None,
) -> dict[str, Any]:
    """
    既存 inventory / verified_environment を再利用し、欠落は unknown。
    """
    inventory = inventory or {}
    verified = verified_environment or {}

    platform_name = (
        inventory.get("platform")
        or verified.get("platform")
        or platform.system()
        or UNKNOWN
    )
    os_family = normalize_os_family(str(platform_name))

    os_version = UNKNOWN
    try:
        release = platform.release()
        version = platform.version()
        if release or version:
            os_version = " ".join(p for p in (release, version) if p).strip() or UNKNOWN
    except Exception:
        os_version = UNKNOWN

    available_commands = []
    if inventory.get("available_commands"):
        available_commands = [
            str(x) for x in inventory.get("available_commands") or [] if str(x).strip()
        ]
    else:
        for item in inventory.get("commands") or []:
            if isinstance(item, dict) and item.get("available") and item.get("name"):
                available_commands.append(str(item["name"]))

    available_modules = []
    if inventory.get("available_modules"):
        available_modules = [
            str(x) for x in inventory.get("available_modules") or [] if str(x).strip()
        ]
    else:
        for item in inventory.get("modules") or []:
            if isinstance(item, dict) and item.get("available") and item.get("name"):
                available_modules.append(str(item["name"]))

    runtime = str(verified.get("language") or "python")
    runtime_version = str(
        verified.get("python_full_version")
        or verified.get("python_version")
        or f"{sys.version_info.major}.{sys.version_info.minor}"
    )
    architecture = str(
        verified.get("architecture") or platform.machine() or UNKNOWN
    )

    return {
        "os_family": os_family,
        "os_name": str(platform_name).lower() if platform_name else UNKNOWN,
        "os_version": os_version,
        "architecture": architecture or UNKNOWN,
        "shell": _detect_shell(),
        "runtime": runtime or UNKNOWN,
        "runtime_version": runtime_version or UNKNOWN,
        "privilege": _privilege_level(),
        "available_commands": sorted(set(c.lower() for c in available_commands)),
        "available_modules": sorted(set(m.lower() for m in available_modules)),
        "phase": "kss-phase-b",
        "source": "environment_context",
    }


def command_on_path(name: str) -> bool:
    return bool(shutil.which(str(name or "").strip()))
