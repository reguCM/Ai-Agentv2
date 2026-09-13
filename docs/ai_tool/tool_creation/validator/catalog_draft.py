from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_UNKNOWN = "UNKNOWN"


def _permissions_from_spec(spec: dict[str, Any]) -> list[str]:
    perms = spec.get("required_permission")
    if isinstance(perms, list) and perms:
        return [str(p) for p in perms]
    return [_UNKNOWN]


def _catalog_status(spec: dict[str, Any], key: str, allowed: set[str]) -> str:
    hints = spec.get("catalog_hints")
    if isinstance(hints, dict) and key in hints:
        value = str(hints[key])
        if value in allowed:
            return value
        return _UNKNOWN
    return _UNKNOWN


def generate_catalog_draft(spec: dict[str, Any], *, spec_ref: str | None = None) -> dict[str, Any]:
    """Mechanical mapping only. No registry writes. Missing fields -> UNKNOWN."""
    draft: dict[str, Any] = {
        "tool_id": spec.get("tool_id", _UNKNOWN),
        "name": spec.get("name", _UNKNOWN),
        "provider": spec.get("provider", _UNKNOWN),
        "version": spec.get("version", _UNKNOWN),
        "description": spec.get("description", _UNKNOWN),
        "capabilities": list(spec.get("capability") or []),
        "input_schema": spec.get("input_schema") if isinstance(spec.get("input_schema"), dict) else {},
        "output_schema": spec.get("output_schema"),
        "side_effect": spec.get("side_effect", _UNKNOWN),
        "permissions": _permissions_from_spec(spec),
        "network_access": spec.get("network_access") if isinstance(spec.get("network_access"), bool) else _UNKNOWN,
        "filesystem_access": spec.get("filesystem_access", _UNKNOWN),
        "risk_level": spec.get("risk_level", _UNKNOWN),
        "cost": spec.get("cost", _UNKNOWN),
        "tool_status": spec.get("tool_status", _UNKNOWN),
        "experiment_status": _catalog_status(
            spec,
            "experiment_status",
            {"unknown", "experimental", "tested", "unsupported"},
        ),
        "adoption_status": _catalog_status(
            spec,
            "adoption_status",
            {"not_reviewed", "candidate", "approved", "rejected"},
        ),
        "spec_ref": spec_ref or _UNKNOWN,
        "provider_specific": spec.get("provider_specific") if isinstance(spec.get("provider_specific"), dict) else {},
        "_draft_meta": {
            "generated_by": "tool_creation.validator.catalog_draft",
            "registry_modified": False,
            "inferred_fields": [],
        },
    }

    if draft["experiment_status"] == _UNKNOWN:
        draft["_draft_meta"]["inferred_fields"].append("experiment_status")
    if draft["adoption_status"] == _UNKNOWN:
        draft["_draft_meta"]["inferred_fields"].append("adoption_status")

    return draft


def write_catalog_draft(
    spec: dict[str, Any],
    output_dir: Path,
    *,
    spec_ref: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    tool_id = str(spec.get("tool_id") or "UNKNOWN")
    safe_name = tool_id.replace(":", "_")
    path = output_dir / f"{safe_name}.json"
    draft = generate_catalog_draft(spec, spec_ref=spec_ref)
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
