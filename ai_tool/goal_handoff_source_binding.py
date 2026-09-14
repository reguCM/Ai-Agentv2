"""Deterministic references from a Goal Handoff to Mission canonical identities."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_handoff_source_binding(
    mission: Mapping[str, Any],
) -> dict[str, Any]:
    mission_id = str(mission.get("mission_id") or "").strip()
    if not mission_id:
        raise ValueError("missing_mission_id")

    requirement_ids = [
        str(row.get("requirement_id") or "").strip()
        for row in (mission.get("structured_requirements") or [])
        if isinstance(row, Mapping)
    ]
    if not requirement_ids or any(not item for item in requirement_ids):
        raise ValueError("missing_requirement_id")
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("duplicate_requirement_id")

    return {
        "mission_id": mission_id,
        "requirement_ids": sorted(requirement_ids),
    }


def validate_handoff_source_binding(
    packet: Mapping[str, Any],
    mission: Mapping[str, Any] | None,
) -> list[str]:
    binding = packet.get("source_binding")
    if not isinstance(binding, Mapping):
        return ["missing_source_binding"]
    if not isinstance(mission, Mapping):
        return ["source_mission_not_found"]

    errors: list[str] = []
    mission_id = str(mission.get("mission_id") or "").strip()
    if str(binding.get("mission_id") or "").strip() != mission_id:
        errors.append("source_mission_mismatch")

    referenced = binding.get("requirement_ids")
    if not isinstance(referenced, Sequence) or isinstance(referenced, (str, bytes)):
        errors.append("invalid_requirement_references")
        return errors
    reference_ids = [str(item or "").strip() for item in referenced]
    if len(reference_ids) != len(set(reference_ids)):
        errors.append("duplicate_requirement_reference")

    canonical_ids = [
        str(row.get("requirement_id") or "").strip()
        for row in (mission.get("structured_requirements") or [])
        if isinstance(row, Mapping)
    ]
    if sorted(reference_ids) != sorted(canonical_ids):
        errors.append("source_requirement_mismatch")
    return sorted(set(errors))


__all__ = ["build_handoff_source_binding", "validate_handoff_source_binding"]
