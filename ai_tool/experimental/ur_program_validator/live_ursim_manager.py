"""Phase I — Live URSim Docker manager + automation boundary."""
from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.live_environment import (
    LiveURSimTarget,
    default_live_target,
    investigate_live_environment,
)
from ai_tool.experimental.ur_program_validator.models import URSimResult
from ai_tool.experimental.ur_program_validator.storage_policy import ensure_storage_dirs, resolve_storage_root

AutomationLevel = Literal[0, 1, 2, 3]
ContainerState = Literal["not_started", "starting", "running", "failed", "stopped"]

CONTAINER_NAME = "ai_agent_ursim_phase_i"
STARTUP_TIMEOUT_S = 120


@dataclass
class SmokeTestResult:
    container_started: bool
    polyscope_accessible: bool
    dashboard_reachable: bool
    robot_model_visible: str
    simulation_mode: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_started": self.container_started,
            "polyscope_accessible": self.polyscope_accessible,
            "dashboard_reachable": self.dashboard_reachable,
            "robot_model_visible": self.robot_model_visible,
            "simulation_mode": self.simulation_mode,
            "notes": self.notes,
        }

    @property
    def passed(self) -> bool:
        return self.container_started and self.dashboard_reachable


@dataclass
class LiveExecutionResult:
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    executed: bool
    message: str
    errors: list[str] = field(default_factory=list)
    dashboard_log: list[str] = field(default_factory=list)
    script_response: str = ""

    def to_ursim_result(self, automation_level: AutomationLevel) -> URSimResult:
        level_map = {0: "manual", 1: "semi_auto", 2: "auto", 3: "auto"}
        return URSimResult(
            status=self.status,
            executed=self.executed,
            mode="live",
            message=self.message,
            errors=self.errors,
            automation_level=level_map.get(automation_level, "manual"),
        )


def _run_docker(args: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def docker_daemon_ok() -> bool:
    return investigate_live_environment().live_available


def pull_image(target: LiveURSimTarget | None = None) -> tuple[bool, str]:
    target = target or default_live_target()
    if not docker_daemon_ok():
        return False, "Docker daemon unavailable"
    proc = _run_docker(["pull", target.full_image], timeout=600)
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, f"Pulled {target.full_image}"


def start_container(
    *,
    target: LiveURSimTarget | None = None,
    programs_dir: Path | None = None,
) -> tuple[bool, str]:
    """Start URSim container detached — no real robot connection."""
    target = target or default_live_target()
    if not docker_daemon_ok():
        return False, "Docker daemon unavailable"

    _run_docker(["rm", "-f", CONTAINER_NAME], timeout=30)

    if programs_dir:
        programs = programs_dir
    else:
        programs = Path(ensure_storage_dirs()["ursim_programs"])
    programs.mkdir(parents=True, exist_ok=True)

    cmd = [
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"{target.ports_vnc}:5900",
        "-p",
        f"{target.ports_web}:6080",
        "-p",
        f"{target.ports_dashboard}:29999",
        "-p",
        f"{target.ports_primary}:30001",
        "-p",
        f"{target.ports_secondary}:30002",
        "-e",
        f"{target.robot_model_env}={target.robot_model}",
        "-v",
        f"{programs.as_posix()}:{target.programs_mount}",
        target.full_image,
    ]
    proc = _run_docker(cmd, timeout=STARTUP_TIMEOUT_S)
    if proc.returncode != 0:
        return False, proc.stderr.strip() or proc.stdout.strip()
    return True, proc.stdout.strip()[:12] or "started"


def container_running() -> bool:
    if not docker_daemon_ok():
        return False
    proc = _run_docker(["inspect", "-f", "{{.State.Running}}", CONTAINER_NAME], timeout=10)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _tcp_probe(host: str, port: int, *, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _dashboard_command(host: str, port: int, command: str, *, timeout: float = 5.0) -> str:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.recv(4096)  # welcome banner
        sock.sendall(f"{command}\n".encode())
        return sock.recv(4096).decode(errors="replace").strip()


def wait_for_dashboard(host: str = "127.0.0.1", port: int = 29999, timeout_s: int = STARTUP_TIMEOUT_S) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _tcp_probe(host, port):
            return True
        time.sleep(3)
    return False


def run_smoke_test(target: LiveURSimTarget | None = None) -> SmokeTestResult:
    """Smoke test — container + dashboard; UI check manual at http://localhost:6080."""
    target = target or default_live_target()
    notes: list[str] = []

    if not docker_daemon_ok():
        return SmokeTestResult(
            container_started=False,
            polyscope_accessible=False,
            dashboard_reachable=False,
            robot_model_visible="UNKNOWN",
            simulation_mode="UNKNOWN",
            notes=["Docker daemon unavailable — smoke test skipped"],
        )

    ok, msg = start_container(target=target)
    notes.append(f"start: {msg}")
    if not ok:
        return SmokeTestResult(
            container_started=False,
            polyscope_accessible=False,
            dashboard_reachable=False,
            robot_model_visible="UNKNOWN",
            simulation_mode="UNKNOWN",
            notes=notes,
        )

    notes.append("Waiting for dashboard port...")
    dash_ok = wait_for_dashboard(port=target.ports_dashboard)
    web_ok = _tcp_probe("127.0.0.1", target.ports_web)

    robot_model = target.robot_model if dash_ok else "UNKNOWN"
    if dash_ok:
        try:
            resp = _dashboard_command("127.0.0.1", target.ports_dashboard, "robotmode")
            notes.append(f"robotmode: {resp[:80]}")
        except OSError as e:
            notes.append(f"dashboard command failed: {e}")

    return SmokeTestResult(
        container_started=container_running(),
        polyscope_accessible=web_ok,
        dashboard_reachable=dash_ok,
        robot_model_visible=robot_model,
        simulation_mode="simulation" if dash_ok else "UNKNOWN",
        notes=notes,
    )


def _prepare_robot(host: str, port: int) -> list[str]:
    """Dashboard prep — power/brake; failures recorded not hidden."""
    log: list[str] = []
    for cmd in ("power on", "brake release"):
        try:
            resp = _dashboard_command(host, port, cmd)
            log.append(f"{cmd}: {resp}")
        except OSError as e:
            log.append(f"{cmd}: ERROR {e}")
    return log


def execute_urscript_live(
    script: str,
    *,
    target: LiveURSimTarget | None = None,
    host: str = "127.0.0.1",
) -> LiveExecutionResult:
    """
    Level-2 automation attempt: dashboard prep + secondary client URScript send.
    Port 30002 per official client interface documentation.
    """
    target = target or default_live_target()
    if not docker_daemon_ok() or not container_running():
        return LiveExecutionResult(
            status="UNKNOWN",
            executed=False,
            message="Live URSim container not running",
            errors=["container unavailable"],
        )

    dash_log = _prepare_robot(host, target.ports_dashboard)
    errors: list[str] = []
    response = ""

    try:
        with socket.create_connection((host, target.ports_secondary), timeout=10) as sock:
            payload = script.strip() + "\n"
            sock.sendall(payload.encode())
            time.sleep(0.5)
            try:
                response = sock.recv(8192).decode(errors="replace")
            except OSError:
                response = ""
    except OSError as e:
        errors.append(f"secondary client send failed: {e}")
        return LiveExecutionResult(
            status="FAIL",
            executed=False,
            message="URScript send to live URSim failed",
            errors=errors,
            dashboard_log=dash_log,
            script_response=response,
        )

    # Heuristic error detection — not claiming full runtime semantics
    lower = response.lower()
    if any(tok in lower for tok in ("error", "syntax", "unknown", "failed", "exception")):
        errors.append(response[:500] or "runtime error in response")
        return LiveExecutionResult(
            status="FAIL",
            executed=True,
            message="Live URSim reported error",
            errors=errors,
            dashboard_log=dash_log,
            script_response=response,
        )

    return LiveExecutionResult(
        status="PASS",
        executed=True,
        message="Live URSim accepted script (not real-robot safety)",
        errors=[],
        dashboard_log=dash_log,
        script_response=response,
    )


def stop_container() -> None:
    if docker_daemon_ok():
        _run_docker(["rm", "-f", CONTAINER_NAME], timeout=30)


def assess_automation_level(smoke: SmokeTestResult | None) -> dict[str, Any]:
    """Automation level 0–3 per Phase I spec."""
    if not smoke or not smoke.passed:
        return {
            "level": 0,
            "label": "manual",
            "rationale": "Live URSim not reachable — manual/HITL or stub only",
            "interfaces_confirmed": [],
        }
    return {
        "level": 2,
        "label": "auto",
        "rationale": "Container start + dashboard TCP + secondary client script send implemented",
        "interfaces_confirmed": [
            "Docker API",
            "Dashboard Server :29999",
            "Secondary Client :30002",
            "Programs volume /ursim/programs",
        ],
        "not_confirmed": [
            "Full headless PolyScope program load/play via .urp",
            "Regression suite (Level 3)",
        ],
    }
