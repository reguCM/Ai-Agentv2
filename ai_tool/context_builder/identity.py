from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolIdentity:
    tool_id: str
    canonical_id: str
    name: str
    provider: str
    spec_path: str | None
    registry_entry: dict[str, Any] | None
    spec: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        module = None
        function = None
        if self.spec and isinstance(self.spec.get("provider_specific"), dict):
            ps = self.spec["provider_specific"]
            module = ps.get("implementation_module") or ps.get("module")
            function = ps.get("implementation_function") or ps.get("function")
        if self.registry_entry:
            module = module or self.registry_entry.get("module")
            function = function or self.registry_entry.get("function")
        return {
            "tool_id": self.tool_id,
            "canonical_id": self.canonical_id,
            "name": self.name,
            "provider": self.provider,
            "spec_path": self.spec_path,
            "module": module,
            "function": function,
            "registry_name": self.registry_entry.get("name") if self.registry_entry else None,
            "visibility": (
                (self.spec or {}).get("required_permission")
                or ([f"visibility:{self.registry_entry.get('visibility')}"]
                    if self.registry_entry and self.registry_entry.get("visibility")
                    else None)
            ),
        }


def normalize_tool_id(tool_id: str, aliases: dict[str, str]) -> str:
    raw = tool_id.strip()
    if raw in aliases:
        return aliases[raw]
    if ":" in raw:
        return raw
    return f"local:{raw}"


def resolve_identity(
    tool_id: str,
    *,
    repo_root: Path,
    rules: dict[str, Any],
) -> ToolIdentity | None:
    aliases = rules.get("aliases") or {}
    canonical = normalize_tool_id(tool_id, aliases)
    tool_rules = (rules.get("tool_specific") or {}).get(canonical)

    spec_path: str | None = None
    spec: dict[str, Any] | None = None
    if tool_rules and tool_rules.get("spec_path"):
        spec_path = str(tool_rules["spec_path"])
        full = repo_root / spec_path.replace("/", "\\") if "\\" in str(repo_root) else repo_root / spec_path
        if full.is_file():
            spec = json.loads(full.read_text(encoding="utf-8"))
    else:
        guessed = repo_root / "docs" / "ai_tool" / "tool_creation" / "specs" / f"{canonical.replace(':', '_')}.json"
        if guessed.is_file():
            spec_path = guessed.relative_to(repo_root).as_posix()
            spec = json.loads(guessed.read_text(encoding="utf-8"))

    name = canonical.split(":", 1)[-1]
    provider = canonical.split(":", 1)[0] if ":" in canonical else "local"

    registry_entry = _lookup_registry(name, repo_root)
    if spec:
        name = spec.get("name") or name
        provider = spec.get("provider") or provider

    if spec is None and registry_entry is None and tool_rules is None:
        return None

    return ToolIdentity(
        tool_id=tool_id,
        canonical_id=canonical,
        name=name,
        provider=provider,
        spec_path=spec_path,
        registry_entry=registry_entry,
        spec=spec,
    )


def _lookup_registry(name: str, repo_root: Path) -> dict[str, Any] | None:
    registry_path = repo_root / "registry" / "tools.json"
    if not registry_path.is_file():
        return None
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in data.get("tools") or []:
        if entry.get("name") == name:
            return entry
    return None
