"""Deterministic plan fingerprint for Test Safety authorization (S5a)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from test_safety.validator import DIMENSION_KEYS

_VALID_LEVELS = frozenset({"LEVEL_1", "LEVEL_2", "LEVEL_3"})
_VALID_DIM_STATES = frozenset({"NONE", "CONTROLLED", "PRESENT", "UNKNOWN"})


def _normalize_commands(commands: Any) -> list[str]:
    if not commands:
        return []
    return [str(c).strip() for c in commands if str(c).strip()]


def fingerprint_material_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """
    Canonical safety inputs used by evaluate_test_plan (excluding host_process_notes).

    Excludes: plan_id, description, notes, reference_case_id, timestamps, observations.
    """
    commands = _normalize_commands(plan.get("commands"))
    if not commands:
        raise ValueError("test_plan.commands required for fingerprint")

    material: dict[str, Any] = {"commands": commands}

    level = plan.get("declared_primary_risk_level")
    if level in _VALID_LEVELS:
        material["declared_primary_risk_level"] = level

    declared = plan.get("declared_dimensions")
    if isinstance(declared, Mapping) and declared:
        dims: dict[str, str] = {}
        for key in sorted(DIMENSION_KEYS):
            if key not in declared:
                continue
            value = declared[key]
            if value in _VALID_DIM_STATES:
                dims[key] = value
        if dims:
            material["declared_dimensions"] = dims

    write_scope = plan.get("declared_write_scope")
    if write_scope:
        scope = sorted({str(x).strip() for x in write_scope if str(x).strip()})
        if scope:
            material["declared_write_scope"] = scope

    return material


def compute_plan_fingerprint(plan: Mapping[str, Any]) -> str:
    """SHA-256 hex of canonical JSON fingerprint material."""
    material = fingerprint_material_from_plan(plan)
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fingerprint_from_evaluation_packet(evaluation_packet: Mapping[str, Any]) -> str:
    test_plan = evaluation_packet.get("test_plan")
    if not isinstance(test_plan, Mapping):
        raise ValueError("evaluation packet missing test_plan")
    return compute_plan_fingerprint(test_plan)
