"""
Phase B: EnvironmentRequirement 抽出と CompatibilityStatus 判定（機械的）。
confirmed は肯定的証拠があるときだけ。unknown != incompatible。
"""

from __future__ import annotations

import re
from typing import Any

from tools.ai.state.environment_context import (
    OS_FAMILY_DARWIN,
    OS_FAMILY_LINUX,
    OS_FAMILY_UNKNOWN,
    OS_FAMILY_WINDOWS,
    UNKNOWN,
    normalize_os_family,
)

COMPAT_CONFIRMED = "confirmed"
COMPAT_LIKELY = "likely"
COMPAT_UNKNOWN = "unknown"
COMPAT_INCOMPATIBLE = "incompatible"

_LINUX_COMMANDS = {
    "bash",
    "sh",
    "df",
    "free",
    "lsblk",
    "uname",
    "apt",
    "apt-get",
    "yum",
    "dnf",
    "systemctl",
}
_WINDOWS_COMMANDS = {
    "powershell",
    "powershell.exe",
    "pwsh",
    "cmd",
    "cmd.exe",
    "wmic",
    "nvidia-smi",
}
_WINDOWS_MARKERS = re.compile(
    r"win32_|get-ciminstance|get-wmiobject|get-counter|get-volume|"
    r"get-psdrive|\\$env:|powershell",
    re.I,
)
_LINUX_MARKERS = re.compile(
    r"\bdf\b|\bfree\b|/proc/|\blsblk\b|systemctl|/sys/",
    re.I,
)


def empty_requirement() -> dict[str, Any]:
    return {
        "claimed_os_family": UNKNOWN,
        "claimed_runtime": UNKNOWN,
        "required_commands": [],
        "required_modules": [],
        "required_architecture": UNKNOWN,
        "minimum_version": UNKNOWN,
        "requires_privilege": UNKNOWN,
    }


def extract_environment_requirement(candidate: dict | None) -> dict[str, Any]:
    """
    Candidate から明示・強い手がかりだけを抽出。推測しすぎない。
    """
    req = empty_requirement()
    if not isinstance(candidate, dict):
        return req

    command = str(candidate.get("command") or "").strip().lower()
    args = candidate.get("args") or []
    script = " ".join(str(a) for a in args)
    blob = f"{command} {script}"

    # 明示フィールドがあれば優先
    for key in (
        "claimed_os_family",
        "claimed_runtime",
        "required_architecture",
        "minimum_version",
        "requires_privilege",
    ):
        if candidate.get(key) not in (None, ""):
            req[key] = str(candidate.get(key)).strip().lower()

    if candidate.get("required_commands"):
        req["required_commands"] = [
            str(x).lower() for x in candidate.get("required_commands") or [] if str(x).strip()
        ]
    if candidate.get("required_modules"):
        req["required_modules"] = [
            str(x).lower() for x in candidate.get("required_modules") or [] if str(x).strip()
        ]

    if req["claimed_os_family"] == UNKNOWN:
        if command in _WINDOWS_COMMANDS or _WINDOWS_MARKERS.search(blob):
            req["claimed_os_family"] = OS_FAMILY_WINDOWS
        elif command in _LINUX_COMMANDS or _LINUX_MARKERS.search(blob):
            req["claimed_os_family"] = OS_FAMILY_LINUX

    if req["claimed_runtime"] == UNKNOWN:
        if command in ("powershell", "pwsh", "powershell.exe"):
            req["claimed_runtime"] = "powershell"
        elif command in ("python", "python3"):
            req["claimed_runtime"] = "python"
        elif command == "wmic":
            req["claimed_runtime"] = "wmic"

    if not req["required_commands"] and command:
        req["required_commands"] = [command]

    # 特権の明示語だけ
    if req["requires_privilege"] == UNKNOWN:
        if re.search(r"runas|elevate|administrator|sudo\b|requires_admin", blob, re.I):
            req["requires_privilege"] = "admin"
        # それ以外は unknown のまま（read-only と推測しない＝安全側ではない。compat 用）

    if req["claimed_os_family"] != UNKNOWN:
        req["claimed_os_family"] = normalize_os_family(req["claimed_os_family"])
    return req


def assess_compatibility(
    env: dict | None,
    requirement: dict | None,
) -> dict[str, Any]:
    """
    機械判定。版情報不足だけでは incompatible にしない。
    非対応の証拠がないだけでは confirmed にしない。
    """
    env = env or {}
    requirement = requirement or empty_requirement()
    host_family = normalize_os_family(env.get("os_family") or env.get("os_name"))
    claimed = normalize_os_family(requirement.get("claimed_os_family"))
    rationale = []
    status = COMPAT_UNKNOWN

    # OS 族の本質的不一致
    if (
        claimed not in (UNKNOWN, OS_FAMILY_UNKNOWN)
        and host_family not in (UNKNOWN, OS_FAMILY_UNKNOWN)
        and claimed != host_family
    ):
        return {
            "status": COMPAT_INCOMPATIBLE,
            "host_os_family": host_family,
            "claimed_os_family": claimed,
            "rationale_codes": ["os_family_mismatch"],
            "details": {
                "host_os_version": env.get("os_version") or UNKNOWN,
                "minimum_version": requirement.get("minimum_version") or UNKNOWN,
            },
        }

    missing_commands = []
    available = {str(x).lower() for x in (env.get("available_commands") or [])}
    inventory_explicit = "available_commands" in (env or {})
    for cmd in requirement.get("required_commands") or []:
        name = str(cmd).lower()
        if name in available:
            continue
        if inventory_explicit:
            missing_commands.append(name)
            continue
        from tools.ai.state.environment_context import command_on_path

        if not command_on_path(name):
            missing_commands.append(name)

    missing_modules = []
    available_modules = {str(x).lower() for x in (env.get("available_modules") or [])}
    for mod in requirement.get("required_modules") or []:
        if str(mod).lower() not in available_modules:
            missing_modules.append(str(mod).lower())

    if missing_commands and claimed == host_family and claimed != UNKNOWN:
        # 必要コマンド不在: 同族でも実行不能に近い → incompatible（実行手段が無い）
        # ただし required が空でなければ。完全未知のコマンド名だけのときは unknown 寄りにもできるが
        # 「powershell が無い」は incompatible が妥当。
        rationale.append("required_command_missing")
        return {
            "status": COMPAT_INCOMPATIBLE,
            "host_os_family": host_family,
            "claimed_os_family": claimed,
            "rationale_codes": rationale + ["missing_commands:" + ",".join(missing_commands)],
            "details": {
                "missing_commands": missing_commands,
                "missing_modules": missing_modules,
                "host_os_version": env.get("os_version") or UNKNOWN,
                "minimum_version": requirement.get("minimum_version") or UNKNOWN,
            },
        }

    if missing_modules:
        rationale.append("required_module_missing")
        # モジュール欠落は実行前に不明寄り（代替があり得る）→ unknown
        return {
            "status": COMPAT_UNKNOWN,
            "host_os_family": host_family,
            "claimed_os_family": claimed,
            "rationale_codes": rationale + ["missing_modules:" + ",".join(missing_modules)],
            "details": {
                "missing_commands": missing_commands,
                "missing_modules": missing_modules,
                "host_os_version": env.get("os_version") or UNKNOWN,
                "minimum_version": requirement.get("minimum_version") or UNKNOWN,
            },
        }

    min_ver = str(requirement.get("minimum_version") or UNKNOWN)
    host_ver = str(env.get("os_version") or UNKNOWN)
    version_gap = min_ver != UNKNOWN and host_ver != UNKNOWN
    # 版の詳細比較はしない（Windows 9 vs 11 を機械的に incompatible にしない）
    if version_gap:
        rationale.append("version_info_present_not_strictly_compared")

    same_family = (
        claimed not in (UNKNOWN, OS_FAMILY_UNKNOWN)
        and host_family not in (UNKNOWN, OS_FAMILY_UNKNOWN)
        and claimed == host_family
    )
    commands_ok = not missing_commands
    claimed_runtime = str(requirement.get("claimed_runtime") or UNKNOWN)
    runtime_ok = True
    if claimed_runtime not in (UNKNOWN, "") and claimed_runtime == "powershell":
        runtime_ok = "powershell" in {
            str(x).lower() for x in (env.get("available_commands") or [])
        }
    elif claimed_runtime not in (UNKNOWN, "") and claimed_runtime == "wmic":
        runtime_ok = "wmic" in {
            str(x).lower() for x in (env.get("available_commands") or [])
        }

    if same_family and commands_ok and not missing_modules and claimed not in (
        UNKNOWN,
        OS_FAMILY_UNKNOWN,
    ):
        if (
            host_ver != UNKNOWN
            and claimed_runtime not in (UNKNOWN, "")
            and runtime_ok
        ):
            status = COMPAT_CONFIRMED
            rationale.append(
                "positive_match_family_commands_runtime_host_version_known"
            )
        else:
            status = COMPAT_LIKELY
            rationale.append("same_os_family_commands_ok")
    elif claimed in (UNKNOWN, OS_FAMILY_UNKNOWN):
        if commands_ok and (requirement.get("required_commands") or []):
            status = COMPAT_UNKNOWN
            rationale.append("claimed_os_unknown_commands_present")
        else:
            status = COMPAT_UNKNOWN
            rationale.append("insufficient_compatibility_evidence")
    else:
        status = COMPAT_UNKNOWN
        rationale.append("insufficient_compatibility_evidence")

    return {
        "status": status,
        "host_os_family": host_family,
        "claimed_os_family": claimed,
        "rationale_codes": rationale or ["compatibility_assessed"],
        "details": {
            "missing_commands": missing_commands,
            "missing_modules": missing_modules,
            "host_os_version": host_ver,
            "minimum_version": min_ver,
            "available_commands": list(env.get("available_commands") or []),
        },
    }
