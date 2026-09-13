"""URSim adapter — live probe + stub boundary for PoC."""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.models import URSimResult, VerificationStatus
from ai_tool.experimental.ur_program_validator.official_sources import investigate_ursim_environment
from ai_tool.experimental.ur_program_validator.version_context import _version_gte

AutomationLevel = Literal["manual", "semi_auto", "auto", "none"]
AdapterMode = Literal["live", "stub", "manual", "unavailable"]


@dataclass
class URSimProbe:
    docker_available: bool
    ursim_detected: bool
    mode: AdapterMode
    automation_level: AutomationLevel
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "docker_available": self.docker_available,
            "ursim_detected": self.ursim_detected,
            "mode": self.mode,
            "automation_level": self.automation_level,
            "notes": self.notes,
        }


def probe_local_ursim() -> URSimProbe:
    """Probe host for URSim/Docker — does not install or connect to real robot."""
    notes: list[str] = []
    docker_ok = shutil.which("docker") is not None
    if docker_ok:
        try:
            proc = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            notes.append(f"docker: {proc.stdout.strip() or proc.stderr.strip()}")
        except (OSError, subprocess.TimeoutExpired) as e:
            notes.append(f"docker probe failed: {e}")
            docker_ok = False
    else:
        notes.append("docker not found in PATH")

    ursim_detected = False
    # No URSim binary assumed on dev PC
    notes.append(f"host OS: {platform.system()} {platform.release()}")
    notes.append("URSim not installed — PoC uses stub adapter")

    mode: AdapterMode = "stub"
    automation: AutomationLevel = "none"
    if ursim_detected:
        mode = "live"
        automation = "semi_auto"
    elif docker_ok:
        mode = "stub"
        automation = "manual"
        notes.append("Docker present but URSim container not started — manual/HITL path")

    return URSimProbe(
        docker_available=docker_ok,
        ursim_detected=ursim_detected,
        mode=mode,
        automation_level=automation,
        notes=notes,
    )


def run_ursim_stub(
    script: str,
    *,
    test_id: str = "",
    expect_runtime_fail: bool = False,
    polyscope_version: str = "5.15",
) -> URSimResult:
    """
    Stub simulation — models URSim behavior for PoC when live URSim unavailable.
    Clearly labeled STUB — not ground truth for real URSim.
    """
    probe = probe_local_ursim()
    errors: list[str] = []

    if "def " not in script:
        errors.append("URSim stub: missing program definition")
    if script.count("(") != script.count(")"):
        errors.append("URSim stub: syntax error — unbalanced parens")

    for fake in ("foo_bar", "pandas.read_csv", "nonexistent_move"):
        if fake.replace(".", "_") in script.replace(".", "_") or fake in script:
            errors.append(f"URSim stub: runtime error — unknown or invalid call near '{fake}'")

    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("movej(") and stripped.endswith(")"):
            inner = stripped[len("movej(") : -1]
            depth = 0
            commas = 0
            for c in inner:
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif c == "," and depth == 0:
                    commas += 1
            if commas == 0:
                errors.append("URSim stub: runtime error — movej wrong argument count")

    if expect_runtime_fail or "RUNTIME_FAIL" in script:
        errors.append("URSim stub: runtime joint limit / unreachable target (not visible to static validator)")

    if "legacy_move" in script and _version_gte(polyscope_version, "5.10"):
        errors.append("URSim stub: runtime — legacy_move not supported on this PolyScope build")

    if errors:
        return URSimResult(
            status="FAIL",
            executed=False,
            mode=probe.mode,
            message="URSim stub execution failed",
            errors=errors,
            automation_level=probe.automation_level,
        )

    return URSimResult(
        status="PASS",
        executed=True,
        mode="stub",
        message="URSim stub execution succeeded (simulation boundary — not real robot)",
        errors=[],
        automation_level=probe.automation_level,
    )


def run_ursim(
    script: str,
    *,
    test_id: str = "",
    expect_runtime_fail: bool = False,
    polyscope_version: str = "5.15",
) -> URSimResult:
    """Run via live URSim if available, else stub."""
    probe = probe_local_ursim()
    if probe.mode == "live" and probe.ursim_detected:
        return URSimResult(
            status="UNKNOWN",
            executed=False,
            mode="live",
            message="Live URSim automation not implemented in PoC — manual HITL required",
            errors=["automation gap"],
            automation_level="manual",
        )
    return run_ursim_stub(
        script,
        test_id=test_id,
        expect_runtime_fail=expect_runtime_fail,
        polyscope_version=polyscope_version,
    )
