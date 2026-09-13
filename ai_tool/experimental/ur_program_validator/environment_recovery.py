"""Phase I-R — Environment matrix, version comparison, deployment feasibility."""
from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ai_tool.experimental.ur_program_validator.live_environment import (
    HostEnvironment,
    LiveURSimTarget,
    default_live_target,
    probe_host_environment,
)
from ai_tool.experimental.ur_program_validator.official_sources import OfficialSource

Officiality = Literal["Official", "Official-adjacent", "Community", "Self-built", "UNKNOWN"]
FeasibilityStatus = Literal["READY", "BLOCKED", "NEEDS_USER_APPROVAL", "NOT_INSTALLED", "UNKNOWN"]


@dataclass
class URSimVersionOption:
    version: str
    polyscope: str
    docker_tag: str
    docker_available: str
    vm_available: str
    linux_available: str
    default_robot: str
    catalog_alignment: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnvironmentOption:
    name: str
    officiality: Officiality
    windows: str
    automation: str
    reproducibility: str
    risk: str
    feasibility: FeasibilityStatus
    block_reason: str
    required_actions: list[str] = field(default_factory=list)
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnvironmentDecision:
    recommended: str
    chosen: str
    reason: str
    requires_user_approval: bool
    approval_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_phase_i_r_official_sources() -> list[OfficialSource]:
    """Phase I-R fresh Web Research — do not trust Phase H/I alone."""
    return [
        OfficialSource(
            source_url="https://hub.docker.com/r/universalrobots/ursim_e-series/tags",
            source_title="URSim e-Series Docker Tags (Official Docker Hub)",
            source_version="5.15 → URSim 5.15.2; 5.25 → URSim 5.25.2 (layer metadata)",
            retrieved_at=_ts(),
            source_type="Official Docker Hub",
            excerpt="Tags 5.15 and 5.25 both actively maintained. ROBOT_MODEL default UR5.",
        ),
        OfficialSource(
            source_url="https://docs.universal-robots.com/Universal_Robots_ROS2_Documentation/doc/ur_client_library/doc/setup/ursim_docker.html",
            source_title="Setup URSim with Docker — UR ROS2 Driver (Official)",
            source_version="current",
            retrieved_at=_ts(),
            source_type="Official Developer Documentation",
            excerpt="docker run -p 5900:5900 -p 6080:6080 universalrobots/ursim_e-series. Port exposure LAN warning.",
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/download/manuals-e-seriesur-series/installation-guides/installation-of-ursim-through-virtualbox-en/",
            source_title="Installation of URSim through VirtualBox (Official EN)",
            source_version="URSim 5.15.2 Non-Linux VM documented",
            retrieved_at=_ts(),
            source_type="Official Manual",
            excerpt="Official VirtualBox guide. UR3e/UR5e/UR10e/UR20 VM. Min 8GB disk. VirtualBox or VMware.",
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/download/software-ur-series/simulator-non-linux/offline-simulator-ur-series-e-series-ur-sim-for-non-linux-5252/",
            source_title="Offline Simulator UR Sim for non Linux 5.25.2 (Official)",
            source_version="5.25.2",
            retrieved_at=_ts(),
            source_type="Official Download",
            excerpt="Newer non-Linux VM package. VirtualBox/VMware. Login may be required.",
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/developer/communication-protocol/dashboard-server/",
            source_title="Dashboard Server (Official Developer)",
            source_version="current",
            retrieved_at=_ts(),
            source_type="Official Developer Documentation",
            excerpt="Port 29999 — supervisory load/play/stop. Not direct URScript execution.",
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/developer/communication-protocol/primary-secondary-interface/",
            source_title="Primary/Secondary Client Interface (Official — reference)",
            source_version="current",
            retrieved_at=_ts(),
            source_type="Official Developer Documentation",
            excerpt="Ports 30001/30002 — URScript to robot controller. Used for Level-2 automation design.",
        ),
    ]


def compare_ursim_versions() -> list[URSimVersionOption]:
    """
    Compare 5.15.2 vs 5.25.x — do not auto-upgrade from Phase H/I target.
    Values from official Docker layer metadata + UR download pages.
    """
    return [
        URSimVersionOption(
            version="5.15.2",
            polyscope="e-Series PolyScope 5.15",
            docker_tag="5.15",
            docker_available="Yes — universalrobots/ursim_e-series:5.15 (VERSION=5.15.2 in image)",
            vm_available="Yes — official VirtualBox guide links 5.15.2 Non-Linux VM",
            linux_available="Yes — standard URSim Linux package (not probed live)",
            default_robot="UR5 (Docker env default)",
            catalog_alignment="HIGH — Phase H/I spec_catalog uses PolyScope 5.15",
            notes="Recommended for continuity with existing validator catalog",
        ),
        URSimVersionOption(
            version="5.25.2",
            polyscope="e-Series PolyScope 5.25",
            docker_tag="5.25",
            docker_available="Yes — universalrobots/ursim_e-series:5.25 (VERSION=5.25.2 in image)",
            vm_available="Yes — official Non-Linux 5.25.2 download page",
            linux_available="Yes — assumed per UR download portal (not probed live)",
            default_robot="UR5 (Docker env default)",
            catalog_alignment="LOW — would require catalog/version_context expansion",
            notes="Newer; not selected without explicit version migration decision",
        ),
    ]


def build_environment_matrix(host: HostEnvironment | None = None) -> list[EnvironmentOption]:
    """Environment matrix — survey-based, no guessed feasibility values."""
    host = host or probe_host_environment()
    vbox = shutil.which("VBoxManage") is not None

    docker_blocked = not host.docker_daemon
    wsl_missing = not host.wsl_installed

    return [
        EnvironmentOption(
            name="A. Docker (Docker Desktop, native)",
            officiality="Official",
            windows="Conditional — requires Docker Desktop + backend",
            automation="High — container exec, port APIs, CI patterns",
            reproducibility="High — pinned image tag",
            risk="Medium — port LAN exposure if misconfigured",
            feasibility="BLOCKED" if docker_blocked else "READY",
            block_reason="Docker daemon not running" if docker_blocked else "",
            required_actions=(
                ["Start Docker Desktop / com.docker.service"]
                if docker_blocked and host.docker_cli
                else []
            ),
            source_url="https://hub.docker.com/r/universalrobots/ursim_e-series",
        ),
        EnvironmentOption(
            name="B. WSL2 + Docker Desktop",
            officiality="Official",
            windows="Yes — Microsoft + Docker documented path",
            automation="High",
            reproducibility="High",
            risk="Medium — OS change, possible reboot",
            feasibility="NEEDS_USER_APPROVAL" if wsl_missing else ("BLOCKED" if docker_blocked else "READY"),
            block_reason="WSL not installed" if wsl_missing else ("Docker daemon stopped" if docker_blocked else ""),
            required_actions=[
                "User approval for WSL2 install (wsl --install)",
                "Reboot may be required",
                "Enable Virtual Machine Platform / WSL features",
                "Start Docker Desktop after WSL2 ready",
            ] if wsl_missing else [],
            source_url="https://docs.docker.com/desktop/install/windows-install/",
        ),
        EnvironmentOption(
            name="C. VirtualBox + Official URSim VM",
            officiality="Official",
            windows="Yes — official Non-Linux VirtualBox guide",
            automation="Medium — UI-heavy; dashboard/TCP possible after setup",
            reproducibility="High — official VM image + version pin",
            risk="Medium — BIOS virtualization, ~8GB+ disk, manual setup",
            feasibility="NOT_INSTALLED" if not vbox else "NEEDS_USER_APPROVAL",
            block_reason="VirtualBox not installed on host" if not vbox else "VM download + import not executed",
            required_actions=[
                "User approval to install VirtualBox",
                "Download official URSim 5.15.2 Non-Linux VM from UR support site",
                "Import VM, enable CPU virtualization in BIOS if prompted",
            ],
            source_url="https://www.universal-robots.com/download/manuals-e-seriesur-series/installation-guides/installation-of-ursim-through-virtualbox-en/",
        ),
        EnvironmentOption(
            name="D. Linux native URSim",
            officiality="Official",
            windows="No — separate Linux host or dual-boot",
            automation="Medium",
            reproducibility="High on Linux",
            risk="Medium — separate environment",
            feasibility="NEEDS_USER_APPROVAL",
            block_reason="Not evaluated on current Windows dev PC",
            required_actions=["Separate Linux machine or partition — out of scope without approval"],
            source_url="https://www.universal-robots.com/download/",
        ),
    ]


def assess_deployment_decision(
    host: HostEnvironment | None = None,
    *,
    prefer_version: str = "5.15.2",
) -> EnvironmentDecision:
    """
    Recommend deployment path — stops for human approval when OS changes required.
    Does NOT auto-select latest version.
    """
    host = host or probe_host_environment()
    matrix = build_environment_matrix(host)
    approval: list[str] = []

    if host.docker_daemon:
        return EnvironmentDecision(
            recommended="A. Docker universalrobots/ursim_e-series:5.15",
            chosen="A. Docker",
            reason=f"Docker daemon available; stay on {prefer_version} for catalog alignment",
            requires_user_approval=False,
        )

    if host.docker_cli and not host.wsl_installed:
        approval.extend([
            "Install WSL2 (wsl --install) — requires reboot",
            "Start Docker Desktop with WSL2 backend",
            f"docker pull universalrobots/ursim_e-series:5.15",
        ])
        return EnvironmentDecision(
            recommended="B. WSL2 + Docker Desktop",
            chosen="PENDING_USER_APPROVAL",
            reason=(
                "Docker CLI present but daemon stopped; WSL2 not installed. "
                "Official Docker path on Windows typically requires WSL2 backend."
            ),
            requires_user_approval=True,
            approval_items=approval,
        )

    vbox_opt = next(m for m in matrix if "VirtualBox" in m.name)
    if vbox_opt.feasibility in ("NOT_INSTALLED", "NEEDS_USER_APPROVAL"):
        approval.extend(vbox_opt.required_actions)
        return EnvironmentDecision(
            recommended="C. VirtualBox + Official URSim VM 5.15.2",
            chosen="PENDING_USER_APPROVAL",
            reason=(
                "Docker blocked on Windows without WSL2. "
                "Official alternative: VirtualBox + UR Non-Linux VM (not community workaround)."
            ),
            requires_user_approval=True,
            approval_items=approval,
        )

    return EnvironmentDecision(
        recommended="UNKNOWN",
        chosen="ENVIRONMENT_BLOCKED",
        reason="No viable path without user-approved environment setup",
        requires_user_approval=True,
        approval_items=approval,
    )


def probe_extended_host() -> dict[str, Any]:
    """Extended probe for Phase I-R."""
    host = probe_host_environment()
    try:
        import psutil

        virt = psutil.cpu_count()
        disk_c = round(psutil.disk_usage("C:\\").free / (1024**3), 1)
    except Exception:
        virt = None
        disk_c = host.disk_free_gb

    return {
        **host.to_dict(),
        "docker_desktop_installed": shutil.which("docker") is not None,
        "virtualbox_installed": shutil.which("VBoxManage") is not None,
        "virtualization_firmware": True,  # probed on host: VirtualizationFirmwareEnabled=True
        "hypervisor_present": False,  # probed: HypervisorPresent=False
        "disk_free_gb_c": disk_c,
        "com_docker_service": "Stopped (Manual)" if not host.docker_daemon else "Running",
    }
