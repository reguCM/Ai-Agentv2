"""Official source provenance from Web Research (Phase H)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai_tool.experimental.development_assistance.fixtures import FIXTURE_URSCRIPT, FIXTURE_UR_API


@dataclass
class OfficialSource:
    source_url: str
    source_title: str
    source_version: str
    retrieved_at: str
    source_type: str
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class URSimEnvironmentInfo:
    name: str = "URSim"
    target_robot: str = "UR3e (typical — verify for your license)"
    polyscope_version: str = "UNKNOWN"
    ur_sim_version: str = "UNKNOWN"
    supported_os: list[str] = field(default_factory=list)
    docker_supported: str = "UNKNOWN"
    vm_supported: str = "UNKNOWN"
    linux_supported: str = "UNKNOWN"
    windows_host: str = "UNKNOWN"
    cpu_requirement: str = "UNKNOWN"
    ram_requirement: str = "UNKNOWN"
    gpu_requirement: str = "UNKNOWN"
    disk_requirement: str = "UNKNOWN"
    license_conditions: str = "UNKNOWN"
    installation_method: str = "UNKNOWN"
    known_limitations: list[str] = field(default_factory=list)
    local_availability: str = "UNKNOWN"
    provenance: list[OfficialSource] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **{k: v for k, v in asdict(self).items() if k != "provenance"},
            "provenance": [p.to_dict() for p in self.provenance],
        }


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_official_sources() -> list[OfficialSource]:
    """Sources from TDA fixtures + structured investigation — not LLM memory."""
    return [
        OfficialSource(
            source_url="https://fixture.local/urscript-manual",
            source_title="URScript Manual (fixture — official pattern)",
            source_version="UNKNOWN",
            retrieved_at=_ts(),
            source_type="Official Documentation",
            excerpt=FIXTURE_URSCRIPT.strip()[:300],
        ),
        OfficialSource(
            source_url="https://fixture.local/ur-sdk",
            source_title="Universal Robots SDK (fixture)",
            source_version="UNKNOWN",
            retrieved_at=_ts(),
            source_type="Official Documentation",
            excerpt=FIXTURE_UR_API.strip()[:200],
        ),
        OfficialSource(
            source_url="https://www.universal-robots.com/articles/ur/interface-communication/ursim/",
            source_title="URSim — Universal Robots (reference URL — not fetched live in PoC)",
            source_version="UNKNOWN",
            retrieved_at=_ts(),
            source_type="Official Documentation",
            excerpt="URSim virtual robot environment — verify version/OS on download page before install.",
        ),
    ]


def investigate_ursim_environment() -> URSimEnvironmentInfo:
    """
    Web Research summary for URSim — explicit UNKNOWNs where not verified live.
    PoC does not conflate historical vs current without evidence.
    """
    sources = collect_official_sources()
    return URSimEnvironmentInfo(
        name="URSim",
        target_robot="UR3e — confirm against installed URSim package",
        polyscope_version="UNKNOWN — check URSim release notes at install time",
        ur_sim_version="UNKNOWN — not probed on this host in PoC",
        supported_os=["Linux (common)", "Windows (host-dependent)", "Docker (reported — verify official docs)"],
        docker_supported="LIKELY — official Docker images exist; version not verified in PoC",
        vm_supported="UNKNOWN",
        linux_supported="YES — typical deployment path per official docs pattern",
        windows_host="PARTIAL — often via VM/Docker; native Windows support version-dependent",
        cpu_requirement="UNKNOWN",
        ram_requirement="UNKNOWN — typically several GB; not measured",
        gpu_requirement="NONE typical for URSim",
        disk_requirement="UNKNOWN",
        license_conditions="Universal Robots license terms — verify on download",
        installation_method="Official download / Docker — not executed in PoC",
        known_limitations=[
            "Simulation ≠ real robot safety",
            "I/O simulation limited vs physical wiring",
            "Version-specific URScript features",
        ],
        local_availability="NOT_INSTALLED — PoC uses stub adapter",
        provenance=sources,
    )
