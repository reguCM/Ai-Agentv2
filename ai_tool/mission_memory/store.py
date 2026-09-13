"""Read/write I/O for Mission / Execution / Evidence.

Default production root is local_state/mission_memory/. Callers may inject another root.
Not connected to Chat or Runtime persist.
Execution and Evidence records are create-only. original_goal is not overwritten.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_tool.mission_memory.paths import (
    MissionMemoryError,
    StorePaths,
    default_store_root,
)
from ai_tool.mission_memory.validate import (
    ValidationResult,
    validate_bundle,
    validate_evidence,
    validate_execution,
    validate_mission,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MissionMemoryError(
            "INVALID_JSON",
            f"{path} is not valid JSON: {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise MissionMemoryError("INVALID_JSON", f"{path} is not a JSON object")
    return data


def _write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _reject(result: ValidationResult) -> None:
    details = result.schema_errors + result.join_errors
    raise MissionMemoryError(
        "VALIDATION_REJECTED",
        "; ".join(details) if details else "validation rejected",
    )


class MissionMemoryStore:
    def __init__(self, root: Path) -> None:
        self.paths = StorePaths(Path(root))

    @classmethod
    def from_default(cls) -> MissionMemoryStore:
        return cls(default_store_root())

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        path = self.paths.mission_path(mission_id)
        if not path.is_file():
            return None
        return _read_json(path)

    def get_execution(
        self, mission_id: str, execution_id: str
    ) -> dict[str, Any] | None:
        path = self.paths.execution_path(mission_id, execution_id)
        if not path.is_file():
            return None
        return _read_json(path)

    def get_evidence(self, persistent_evidence_id: str) -> dict[str, Any] | None:
        path = self.paths.evidence_path(persistent_evidence_id)
        if not path.is_file():
            return None
        return _read_json(path)

    def list_executions(self, mission_id: str) -> list[dict[str, Any]]:
        directory = self.paths.execution_dir(mission_id)
        if not directory.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith(".tmp"):
                continue
            records.append(_read_json(path))
        records.sort(
            key=lambda item: (
                int(item.get("execution_sequence") or 0),
                str(item.get("execution_id") or ""),
            )
        )
        return records

    def next_execution_sequence(self, mission_id: str) -> int:
        sequences = [
            item["execution_sequence"]
            for item in self.list_executions(mission_id)
            if isinstance(item.get("execution_sequence"), int)
        ]
        return max(sequences, default=0) + 1

    def put_mission(self, record: dict[str, Any]) -> Path:
        result = validate_mission(record)
        if result.verdict != "ACCEPT":
            _reject(result)
        mission_id = str(record["mission_id"])
        path = self.paths.mission_path(mission_id)
        existing = self.get_mission(mission_id)
        if existing is not None:
            if existing.get("original_goal") != record.get("original_goal"):
                raise MissionMemoryError(
                    "ORIGINAL_GOAL_IMMUTABLE",
                    "original_goal cannot be overwritten",
                )
            if existing.get("mission_id") != record.get("mission_id"):
                raise MissionMemoryError(
                    "INVALID_ID",
                    "mission_id cannot be changed",
                )
        _write_json(path, record)
        return path

    def put_evidence(self, record: dict[str, Any]) -> Path:
        result = validate_evidence(record)
        if result.verdict != "ACCEPT":
            _reject(result)
        persistent_id = str(record["persistent_evidence_id"])
        path = self.paths.evidence_path(persistent_id)
        if path.is_file():
            raise MissionMemoryError(
                "ALREADY_EXISTS",
                f"evidence {persistent_id} already exists",
            )
        created_in = str(record["created_in_mission_id"])
        if self.get_mission(created_in) is None:
            raise MissionMemoryError(
                "NOT_FOUND",
                f"created_in_mission_id {created_in} has no Mission record",
            )
        creator_id = str(record["created_by_execution_id"])
        creator = self.get_execution(created_in, creator_id)
        if creator is not None:
            join = validate_bundle(executions=[creator], evidence=[record])
            if join.verdict != "ACCEPT":
                _reject(join)
        _write_json(path, record)
        return path

    def put_execution(self, record: dict[str, Any]) -> Path:
        schema = validate_execution(record)
        if schema.verdict != "ACCEPT":
            _reject(schema)
        mission_id = str(record["mission_id"])
        execution_id = str(record["execution_id"])
        if self.get_mission(mission_id) is None:
            raise MissionMemoryError(
                "NOT_FOUND",
                f"mission_id {mission_id} has no Mission record",
            )
        path = self.paths.execution_path(mission_id, execution_id)
        if path.is_file():
            raise MissionMemoryError(
                "ALREADY_EXISTS",
                f"execution {execution_id} already exists",
            )
        existing = self.list_executions(mission_id)
        join = validate_bundle(
            mission=self.get_mission(mission_id),
            executions=existing + [record],
        )
        if join.verdict != "ACCEPT":
            _reject(join)
        refs = record.get("evidence_refs") or []
        if not isinstance(refs, list):
            refs = []
        for index, ref in enumerate(refs):
            evidence_id = str(ref)
            loaded = self.get_evidence(evidence_id)
            if loaded is None:
                raise MissionMemoryError(
                    "VALIDATION_REJECTED",
                    f"executions[-1].evidence_refs[{index}]: "
                    f"EVIDENCE_REF_UNRESOLVED {evidence_id}",
                )
            created_in = str(loaded.get("created_in_mission_id") or "")
            created_by = str(loaded.get("created_by_execution_id") or "")
            creator = (
                self.get_execution(created_in, created_by)
                if created_in and created_by
                else None
            )
            if creator is not None:
                creator_refs = [
                    str(item)
                    for item in (creator.get("evidence_refs") or [])
                    if str(item)
                ]
                loaded_evidence = []
                for cref in creator_refs:
                    row = self.get_evidence(cref)
                    if row is not None:
                        loaded_evidence.append(row)
                if evidence_id not in creator_refs:
                    raise MissionMemoryError(
                        "VALIDATION_REJECTED",
                        f"executions[-1].evidence_refs[{index}]: "
                        f"EVIDENCE_REF_NOT_IN_CREATOR {evidence_id}",
                    )
                provenance = validate_bundle(
                    executions=[creator],
                    evidence=loaded_evidence,
                )
                if provenance.verdict != "ACCEPT":
                    _reject(provenance)
        _write_json(path, record)
        return path
