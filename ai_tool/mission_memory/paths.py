"""Store paths for Mission / Execution / Evidence.

Production default is repo-local `local_state/mission_memory/`, not `runs/`.
Tests and callers may still inject another root. Filenames under the root
remain the provisional logical layout.
"""
from __future__ import annotations

import os
from pathlib import Path

MISSIONS_DIR = "missions"
EXECUTIONS_DIR = "executions"
EVIDENCE_DIR = "evidence"
MISSION_FILENAME = "mission.json"
DEFAULT_STORE_RELATIVE = Path("local_state") / "mission_memory"
MISSION_MEMORY_DIR_ENV = "AI_AGENT_MISSION_MEMORY_DIR"

_REPO = Path(__file__).resolve().parents[2]

_UNSAFE_ID_CHARS = set('\\/:\0<>"|?*')


class MissionMemoryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def require_store_id(value: str, *, label: str) -> str:
    """Reject IDs that cannot be a single path segment. Not a schema rule."""
    if not isinstance(value, str) or value == "":
        raise MissionMemoryError("INVALID_ID", f"{label} must be a non-empty string")
    if value.strip() != value:
        raise MissionMemoryError(
            "INVALID_ID",
            f"{label} must not have surrounding whitespace",
        )
    if value in {".", ".."}:
        raise MissionMemoryError("INVALID_ID", f"{label} is not a usable path segment")
    if any(char in _UNSAFE_ID_CHARS for char in value) or any(
        char in value for char in "\r\n"
    ):
        raise MissionMemoryError(
            "INVALID_ID",
            f"{label} contains a character that cannot be a path segment",
        )
    return value


def default_store_root() -> Path:
    """Production root, or AI_AGENT_MISSION_MEMORY_DIR when set.

    Does not create the directory.
    """
    override = str(os.environ.get(MISSION_MEMORY_DIR_ENV) or "").strip()
    if override:
        return Path(override)
    return _REPO / DEFAULT_STORE_RELATIVE


def _contained(path: Path, parent: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise MissionMemoryError(
            "PATH_ESCAPE",
            f"{resolved} is outside {parent}",
        ) from exc
    return resolved


class StorePaths:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def missions_dir(self) -> Path:
        return self.root / MISSIONS_DIR

    def evidence_dir(self) -> Path:
        return self.root / EVIDENCE_DIR

    def mission_dir(self, mission_id: str) -> Path:
        safe = require_store_id(mission_id, label="mission_id")
        return _contained(self.missions_dir() / safe, self.missions_dir())

    def mission_path(self, mission_id: str) -> Path:
        path = self.mission_dir(mission_id) / MISSION_FILENAME
        return _contained(path, self.mission_dir(mission_id))

    def execution_dir(self, mission_id: str) -> Path:
        path = self.mission_dir(mission_id) / EXECUTIONS_DIR
        return _contained(path, self.mission_dir(mission_id))

    def execution_path(self, mission_id: str, execution_id: str) -> Path:
        safe = require_store_id(execution_id, label="execution_id")
        path = self.execution_dir(mission_id) / f"{safe}.json"
        return _contained(path, self.execution_dir(mission_id))

    def evidence_path(self, persistent_evidence_id: str) -> Path:
        safe = require_store_id(
            persistent_evidence_id, label="persistent_evidence_id"
        )
        path = self.evidence_dir() / f"{safe}.json"
        return _contained(path, self.evidence_dir())
