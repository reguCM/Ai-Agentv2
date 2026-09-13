"""Experimental MCP Fetch client — MCP 1.x schema compatibility (does not modify MCPToolProvider)."""
from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class MCPFetchDescriptor:
    tool_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    annotations: dict[str, Any] | None
    server_label: str
    package_version: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MCPFetchCallResult:
    ok: bool
    duration_ms: float
    cold_start_ms: float | None
    is_error: bool
    text_parts: list[str]
    structured_content: Any
    error: str | None
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_server_command() -> list[str]:
    return [sys.executable, "-m", "mcp_server_fetch", "--ignore-robots-txt"]


def _stdio_params() -> StdioServerParameters:
    cmd = _fetch_server_command()
    return StdioServerParameters(command=cmd[0], args=cmd[1:], cwd=str(_REPO_ROOT))


def _schema_from_tool(tool: Any) -> dict[str, Any]:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    if schema is None:
        return {"type": "object"}
    if hasattr(schema, "model_dump"):
        return dict(schema.model_dump())
    if isinstance(schema, dict):
        return dict(schema)
    return {"type": "object"}


def _output_schema_from_tool(tool: Any) -> dict[str, Any] | None:
    schema = getattr(tool, "outputSchema", None) or getattr(tool, "output_schema", None)
    if schema is None:
        return None
    if hasattr(schema, "model_dump"):
        return dict(schema.model_dump())
    if isinstance(schema, dict):
        return dict(schema)
    return None


def _annotations_from_tool(tool: Any) -> dict[str, Any] | None:
    ann = getattr(tool, "annotations", None)
    if ann is None:
        return None
    if hasattr(ann, "model_dump"):
        return dict(ann.model_dump())
    if isinstance(ann, dict):
        return dict(ann)
    return {"repr": repr(ann)}


async def list_fetch_descriptor_async() -> tuple[MCPFetchDescriptor, float]:
    started = time.perf_counter()
    async with stdio_client(_stdio_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            duration_ms = (time.perf_counter() - started) * 1000
            tool = next((t for t in listed.tools if t.name == "fetch"), listed.tools[0])
            pkg_version = None
            try:
                import importlib.metadata as md

                pkg_version = md.version("mcp-server-fetch")
            except Exception:  # noqa: BLE001
                pkg_version = None
            return (
                MCPFetchDescriptor(
                    tool_id=f"mcp:{tool.name}",
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=_schema_from_tool(tool),
                    output_schema=_output_schema_from_tool(tool),
                    annotations=_annotations_from_tool(tool),
                    server_label="mcp-server-fetch",
                    package_version=pkg_version,
                ),
                duration_ms,
            )


async def call_fetch_async(
    arguments: dict[str, Any],
    *,
    reuse_session: bool = False,
    session_bundle: tuple[Any, Any, ClientSession] | None = None,
) -> MCPFetchCallResult:
    started = time.perf_counter()
    cold_start_ms: float | None = None

    async def _call(session: ClientSession) -> Any:
        return await session.call_tool("fetch", arguments)

    try:
        if reuse_session and session_bundle is not None:
            _read, _write, session = session_bundle
            t0 = time.perf_counter()
            result = await _call(session)
            duration_ms = (time.perf_counter() - t0) * 1000
        else:
            async with stdio_client(_stdio_params()) as (read, write):
                async with ClientSession(read, write) as session:
                    init_started = time.perf_counter()
                    await session.initialize()
                    cold_start_ms = (time.perf_counter() - init_started) * 1000
                    t0 = time.perf_counter()
                    result = await _call(session)
                    duration_ms = (time.perf_counter() - t0) * 1000

        is_error = bool(getattr(result, "is_error", None) or getattr(result, "isError", False))
        text_parts = [block.text for block in result.content if getattr(block, "text", None)]
        structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        total_ms = (time.perf_counter() - started) * 1000
        payload = {
            "content": text_parts,
            "structured_content": structured,
            "is_error": is_error,
        }
        if is_error:
            return MCPFetchCallResult(
                ok=False,
                duration_ms=total_ms,
                cold_start_ms=cold_start_ms,
                is_error=True,
                text_parts=text_parts,
                structured_content=structured,
                error="mcp_tool_error",
                raw=payload,
            )
        return MCPFetchCallResult(
            ok=True,
            duration_ms=total_ms,
            cold_start_ms=cold_start_ms,
            is_error=False,
            text_parts=text_parts,
            structured_content=structured,
            error=None,
            raw=payload,
        )
    except Exception as exc:  # noqa: BLE001
        total_ms = (time.perf_counter() - started) * 1000
        return MCPFetchCallResult(
            ok=False,
            duration_ms=total_ms,
            cold_start_ms=cold_start_ms,
            is_error=True,
            text_parts=[],
            structured_content=None,
            error=f"{type(exc).__name__}: {exc}",
            raw={},
        )


def list_fetch_descriptor() -> tuple[MCPFetchDescriptor, float]:
    return asyncio.run(list_fetch_descriptor_async())


def call_fetch(arguments: dict[str, Any], *, reuse_session: bool = False) -> MCPFetchCallResult:
    return asyncio.run(call_fetch_async(arguments, reuse_session=reuse_session))
