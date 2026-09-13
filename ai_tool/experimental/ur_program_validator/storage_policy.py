"""Storage policy — probe C/D usage, prefer D: for movable large data."""
from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Override via env for CI or user preference (must stay absolute)
STORAGE_ROOT_ENV = "AI_AGENT_STORAGE_ROOT"


@dataclass
class DriveUsage:
    letter: str
    total_gb: float
    free_gb: float
    used_gb: float
    exists: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorageLocation:
    category: str
    current_path: str
    recommended_path: str
    movable: bool
    official_method: str
    requires_user_approval: bool
    estimated_size_gb: float | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StorageProbeReport:
    timestamp: str
    drives: list[DriveUsage]
    repo_root: str
    storage_root: str
    locations: list[StorageLocation]
    docker_wsl_c_size_gb: float | None
    policy_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "drives": [d.to_dict() for d in self.drives],
            "repo_root": self.repo_root,
            "storage_root": self.storage_root,
            "locations": [loc.to_dict() for loc in self.locations],
            "docker_wsl_c_size_gb": self.docker_wsl_c_size_gb,
            "policy_notes": self.policy_notes,
        }


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_storage_root(repo_root: Path | None = None) -> Path:
    """
    Movable project data root — prefer D: when available.
    Does NOT relocate Windows/Docker system paths.
    """
    env = os.environ.get(STORAGE_ROOT_ENV, "").strip()
    if env:
        return Path(env).resolve()

    repo = (repo_root or Path.cwd()).resolve()
    # Repo on D: → use sibling data dir on same drive
    if str(repo.drive).upper() == "D:":
        return Path("D:/AI-Agent-data").resolve()
    if Path("D:/").exists():
        return Path("D:/AI-Agent-data").resolve()
    return (repo / "data").resolve()


def probe_drive(letter: str) -> DriveUsage:
    path = f"{letter}:\\"
    if not Path(path).exists():
        return DriveUsage(letter=letter, total_gb=0, free_gb=0, used_gb=0, exists=False)
    try:
        import psutil

        u = psutil.disk_usage(path)
        total = round(u.total / (1024**3), 1)
        free = round(u.free / (1024**3), 1)
        return DriveUsage(letter=letter, total_gb=total, free_gb=free, used_gb=round(total - free, 1), exists=True)
    except ImportError:
        return DriveUsage(letter=letter, total_gb=0, free_gb=0, used_gb=0, exists=Path(path).exists())


def _dir_size_gb(path: Path) -> float | None:
    if not path.exists():
        return None
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        return None
    return round(total / (1024**3), 2)


def standard_paths(repo_root: Path | None = None) -> dict[str, Path]:
    """Canonical paths for Phase I-R-B movable artifacts."""
    root = resolve_storage_root(repo_root)
    return {
        "storage_root": root,
        "runs": root / "runs" / "ai_tool",
        "ursim_programs": root / "ursim" / "programs",
        "docker_smoke": root / "docker_smoke",
        "ursim_pull_cache_note": root / "ursim" / "README.txt",
    }


def ensure_storage_dirs(repo_root: Path | None = None) -> dict[str, str]:
    """Create D:-preferred dirs — project artifacts only, not Docker system."""
    paths = standard_paths(repo_root)
    created: dict[str, str] = {}
    for key, p in paths.items():
        if key.endswith("_note"):
            continue
        p.mkdir(parents=True, exist_ok=True)
        created[key] = str(p)
    note = paths["ursim_pull_cache_note"]
    if not note.exists():
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            "URSim program mounts and run artifacts — AI-Agent storage policy (D: preferred).\n"
            "Docker images remain in Docker Desktop WSL disk unless moved via official UI.\n",
            encoding="utf-8",
        )
    return created


def probe_storage(repo_root: Path | None = None) -> StorageProbeReport:
    repo = (repo_root or Path.cwd()).resolve()
    storage_root = resolve_storage_root(repo)
    local_docker_wsl = Path.home() / "AppData" / "Local" / "Docker" / "wsl"
    docker_wsl_gb = _dir_size_gb(local_docker_wsl)

    drives = [probe_drive("C"), probe_drive("D")]

    locations = [
        StorageLocation(
            category="Project runs / test artifacts",
            current_path=str(repo / "runs" / "ai_tool"),
            recommended_path=str(storage_root / "runs" / "ai_tool"),
            movable=True,
            official_method="Set AI_AGENT_STORAGE_ROOT or use resolve_storage_root() — no junction",
            requires_user_approval=False,
            notes="Repo on D: — prefer storage_root under D:\\AI-Agent-data",
        ),
        StorageLocation(
            category="URSim program mount (Docker -v)",
            current_path=str(repo / "runs" / "ai_tool" / "ursim_programs"),
            recommended_path=str(storage_root / "ursim" / "programs"),
            movable=True,
            official_method="Docker volume mount to D: path in docker run",
            requires_user_approval=False,
        ),
        StorageLocation(
            category="Docker Desktop WSL disk (images/containers)",
            current_path=str(local_docker_wsl),
            recommended_path="D:\\DockerDesktopWSL (example — user chooses)",
            movable=True,
            official_method=(
                "Docker Desktop → Settings → Resources → Advanced → Disk image location "
                "(official — apply before large pulls if possible)"
            ),
            requires_user_approval=True,
            estimated_size_gb=docker_wsl_gb,
            notes="~927MB+ per URSim image; do not use junction/symlink as first choice",
        ),
        StorageLocation(
            category="WSL user distros (Ubuntu etc.)",
            current_path=str(Path.home() / "AppData" / "Local" / "wsl"),
            recommended_path="D:\\WSL (example)",
            movable=True,
            official_method=(
                "wsl --install -d Ubuntu --location D:\\WSL\\Ubuntu (Microsoft Learn); "
                "or .wslconfig distributionInstallPath for new distros"
            ),
            requires_user_approval=True,
            notes="docker-desktop distros managed by Docker Desktop — use Docker UI for those",
        ),
        StorageLocation(
            category="Windows/WSL system",
            current_path="C:\\Windows, C:\\Program Files",
            recommended_path="(do not move)",
            movable=False,
            official_method="N/A — system required",
            requires_user_approval=False,
            notes="Do not forcibly relocate OS components",
        ),
    ]

    policy_notes = [
        "C: large data avoidance — probe before/after any storage change",
        "D: preferred for movable artifacts when official method exists",
        "URSim tag 5.15 image ~1GB; full Docker WSL disk grows with layers",
        f"Baseline Docker WSL on C: {docker_wsl_gb} GB" if docker_wsl_gb is not None else "Docker WSL size unknown",
    ]

    return StorageProbeReport(
        timestamp=_ts(),
        drives=drives,
        repo_root=str(repo),
        storage_root=str(storage_root),
        locations=locations,
        docker_wsl_c_size_gb=docker_wsl_gb,
        policy_notes=policy_notes,
    )


def format_approval_request(report: StorageProbeReport) -> dict[str, Any]:
    """Human-readable approval package for storage changes."""
    pending = [loc for loc in report.locations if loc.requires_user_approval and loc.movable]
    return {
        "requires_approval": len(pending) > 0,
        "items": [
            {
                "category": loc.category,
                "current": loc.current_path,
                "proposed": loc.recommended_path,
                "official_method": loc.official_method,
                "estimated_size_gb": loc.estimated_size_gb,
                "revert": "Docker UI: move disk image back to default path; WSL: export/import or .wslconfig",
            }
            for loc in pending
        ],
        "recommended_timing": "Before docker pull universalrobots/ursim_e-series:5.15 (CHECKPOINT 4)",
        "c_drive_before_gb_free": next((d.free_gb for d in report.drives if d.letter == "C"), None),
        "d_drive_before_gb_free": next((d.free_gb for d in report.drives if d.letter == "D"), None),
    }
