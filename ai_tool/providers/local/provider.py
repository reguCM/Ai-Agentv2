from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from ai_tool.core.models import ToolDescriptor, ToolExecutionResult

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _registry_path() -> Path:
    return _REPO_ROOT / "registry" / "tools.json"


def _registry_input_to_json_schema(input_spec: dict[str, Any]) -> dict[str, Any]:
    """Convert registry/tools.json input format to JSON Schema object."""
    if not input_spec:
        return {"type": "object", "additionalProperties": False}
    properties: dict[str, Any] = {}
    required: list[str] = []
    for key, spec in input_spec.items():
        if not isinstance(spec, dict):
            continue
        prop = {k: v for k, v in spec.items() if k != "required"}
        properties[key] = prop
        if spec.get("required"):
            required.append(key)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _infer_execution_mode(entry: dict[str, Any]) -> str:
    name = str(entry.get("name") or "")
    if any(x in name for x in ("write", "create", "register", "repair", "apply")):
        return "modify"
    if any(x in name for x in ("search", "read", "list", "get", "status")):
        return "read"
    risk = entry.get("risk") or "low"
    if risk == "high":
        return "modify"
    return "read"


class LocalToolProvider:
    """Wraps existing registry/tools.json without modifying it."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or _registry_path()
        self._registry = self._load()

    def _load(self) -> dict[str, Any]:
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def list_descriptors(self, *, visibility: str | None = None) -> list[ToolDescriptor]:
        out: list[ToolDescriptor] = []
        for entry in self._registry.get("tools") or []:
            if visibility and entry.get("visibility") != visibility:
                continue
            name = entry["name"]
            out.append(
                ToolDescriptor(
                    id=f"local:{name}",
                    name=name,
                    provider="local",
                    source=str(self.registry_path),
                    description=entry.get("description") or "",
                    capabilities=list(entry.get("keywords") or []),
                    input_schema=_registry_input_to_json_schema(entry.get("input") or {}),
                    output_schema=None,
                    permissions=[f"visibility:{entry.get('visibility', 'unknown')}"],
                    risk_level=entry.get("risk") or "low",
                    execution_mode=_infer_execution_mode(entry),  # type: ignore[arg-type]
                    availability="local",
                    authentication="none",
                    cost="free",
                    status="available",
                    evidence=["registry/tools.json"],
                    registry_name=name,
                    module=entry.get("module"),
                    function=entry.get("function"),
                    visibility=entry.get("visibility"),
                )
            )
        return out

    def get_descriptor(self, tool_id: str) -> ToolDescriptor | None:
        for d in self.list_descriptors():
            if d.id == tool_id or d.registry_name == tool_id:
                return d
        return None

    def execute(self, tool_id: str, arguments: dict[str, Any] | None = None) -> ToolExecutionResult:
        import time

        descriptor = self.get_descriptor(tool_id)
        if descriptor is None:
            return ToolExecutionResult(
                tool_id=tool_id,
                provider="local",
                ok=False,
                result=None,
                error="tool_not_found",
            )
        if not descriptor.module or not descriptor.function:
            return ToolExecutionResult(
                tool_id=descriptor.id,
                provider="local",
                ok=False,
                result=None,
                error="missing_module_or_function",
            )
        started = time.perf_counter()
        try:
            module = importlib.import_module(descriptor.module)
            fn = getattr(module, descriptor.function)
            payload = fn(**(arguments or {}))
            duration_ms = (time.perf_counter() - started) * 1000
            return ToolExecutionResult(
                tool_id=descriptor.id,
                provider="local",
                ok=True,
                result=payload,
                duration_ms=duration_ms,
            )
        except Exception as exc:  # noqa: BLE001 — experimental provider boundary
            duration_ms = (time.perf_counter() - started) * 1000
            return ToolExecutionResult(
                tool_id=descriptor.id,
                provider="local",
                ok=False,
                result=None,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=duration_ms,
            )


def local_get_current_time() -> dict[str, str]:
    """Read-only local reference implementation for MCP comparison (not in registry)."""
    from datetime import datetime, timezone

    return {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "local",
        "observation_source": "system_clock",
    }
