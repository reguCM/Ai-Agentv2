"""Phase I — fresh official URSim environment research + host probe."""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.ur_program_validator.official_sources import OfficialSource


@dataclass
class HostEnvironment:
    os_name: str
    os_release: str
    cpu: str
    ram_gb: float
    docker_cli: bool
    docker_daemon: bool
    wsl_installed: bool
    gpu_note: str
    disk_free_gb: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveURSimTarget:
    """Single target selected for Phase I — from official Docker Hub docs."""
    image: str
    tag: str
    polyscope_generation: str
    robot_model: str
    ports_vnc: int
    ports_web: int
    ports_dashboard: int
    ports_primary: int
    ports_secondary: int
    programs_mount: str
    robot_model_env: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def full_image(self) -> str:
        return f"{self.image}:{self.tag}"


@dataclass
class LiveEnvironmentReport:
    host: HostEnvironment
    target: LiveURSimTarget
    official_sources: list[OfficialSource]
    live_available: bool
    block_reason: str
    retrieved_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host.to_dict(),
            "target": self.target.to_dict(),
            "official_sources": [s.to_dict() for s in self.official_sources],
            "live_available": self.live_available,
            "block_reason": self.block_reason,
            "retrieved_at": self.retrieved_at,
        }


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_phase_i_official_sources() -> list[OfficialSource]:
    """Fresh Web Research — Phase H info not reused without re-citation."""
    return [
        OfficialSource(
            source_url="https://hub.docker.com/r/universalrobots/ursim_e-series",
            source_title="Universal Robots URSim e-Series Docker Image (Official)",
            source_version="tags 5.9–5.26 (latest updated ~27 days ago)",
            retrieved_at=_ts(),
            source_type="Official Docker Hub",
            excerpt=(
                "Official e-Series URSim. VNC 5900, web UI 6080. "
                "ROBOT_MODEL env: UR3 UR5 UR7 UR10 etc. Programs at /ursim/programs. "
                "Dashboard port 29999 exposable via -p."
            ),
        ),
        OfficialSource(
            source_url="https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/ursim_docker.html",
            source_title="Setup URSim with Docker — UR ROS2 Driver Documentation",
            source_version="current docs",
            retrieved_at=_ts(),
            source_type="Official Developer Documentation",
            excerpt=(
                "docker run -p 5900:5900 -p 6080:6080 universalrobots/ursim_e-series. "
                "Volume mount for programs and urcaps. Default UR5e in examples."
            ),
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/developer/communication-protocol/dashboard-server/",
            source_title="Dashboard Server — Universal Robots Developer",
            source_version="current",
            retrieved_at=_ts(),
            source_type="Official Developer Documentation",
            excerpt="Dashboard Server port 29999 — load/play/stop programs, robot state. TCP newline commands.",
        ),
        OfficialSource(
            source_url="https://hub.docker.com/r/universalrobots/ursim_polyscopex",
            source_title="URSim PolyScope X Docker (Official — not selected for Phase I)",
            source_version="PolyScope X beta",
            retrieved_at=_ts(),
            source_type="Official Docker Hub",
            excerpt="PolyScope X uses web UI port 80. Phase I selects e-Series image for URScript PoC continuity.",
        ),
    ]


def default_live_target() -> LiveURSimTarget:
    """Phase I single target — matches Phase H PolyScope 5.15 catalog."""
    return LiveURSimTarget(
        image="universalrobots/ursim_e-series",
        tag="5.15",
        polyscope_generation="e-Series PolyScope 5.15",
        robot_model="UR5",
        ports_vnc=5900,
        ports_web=6080,
        ports_dashboard=29999,
        ports_primary=30001,
        ports_secondary=30002,
        programs_mount="/ursim/programs",
        robot_model_env="ROBOT_MODEL",
    )


def _docker_daemon_running() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _wsl_installed() -> bool:
    if not shutil.which("wsl"):
        return False
    try:
        proc = subprocess.run(
            ["wsl", "-l", "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).lower()
        if "no installed distributions" in text:
            return False
        if proc.returncode != 0 and "install" in text:
            return False
        # Has at least one distro listed (not header-only)
        lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        return len(lines) > 1
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        return 0.0


def _disk_free_gb() -> float | None:
    try:
        import psutil

        return round(psutil.disk_usage("/").free / (1024**3), 1)
    except ImportError:
        return None


def probe_host_environment() -> HostEnvironment:
    """Probe dev PC — no production changes."""
    cpu = platform.processor() or "unknown"
    try:
        import psutil

        cpu = psutil.cpu_count(logical=False) and f"{psutil.cpu_count(logical=False)} cores" or cpu
    except ImportError:
        pass

    return HostEnvironment(
        os_name=platform.system(),
        os_release=platform.release(),
        cpu=cpu,
        ram_gb=_ram_gb(),
        docker_cli=shutil.which("docker") is not None,
        docker_daemon=_docker_daemon_running(),
        wsl_installed=_wsl_installed(),
        gpu_note="not probed — URSim typically no GPU",
        disk_free_gb=_disk_free_gb(),
    )


def investigate_live_environment() -> LiveEnvironmentReport:
    """Phase I environment — explicit BLOCKED when daemon unavailable."""
    host = probe_host_environment()
    target = default_live_target()
    sources = collect_phase_i_official_sources()

    block_reason = ""
    live_available = False

    if not host.docker_cli:
        block_reason = "Docker CLI not found in PATH"
    elif not host.docker_daemon:
        block_reason = (
            "Docker daemon not running — com.docker.service stopped; "
            "WSL2 backend likely required on Windows (WSL not installed)"
        )
    elif host.ram_gb and host.ram_gb < 8:
        block_reason = f"Insufficient RAM ({host.ram_gb} GB) — URSim image ~927 MB plus host overhead"
    else:
        live_available = True

    return LiveEnvironmentReport(
        host=host,
        target=target,
        official_sources=sources,
        live_available=live_available,
        block_reason=block_reason,
        retrieved_at=_ts(),
    )
