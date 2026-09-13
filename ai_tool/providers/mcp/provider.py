from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ai_tool.core.models import ToolDescriptor, ToolExecutionResult

_REPO_ROOT = Path(__file__).resolve().parents[3]


class MCPToolProvider:
    """Minimal MCP client provider (stdio subprocess). Phase 1: read-only tools only."""

    def __init__(
        self,
        *,
        server_command: list[str] | None = None,
        server_label: str = "ai-tool-time-server",
    ) -> None:
        if server_command is None:
            py = sys.executable
            server_command = [py, "-m", "ai_tool.providers.mcp.time_server"]
        self.server_command = server_command
        self.server_label = server_label

    def _stdio_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.server_command[0],
            args=self.server_command[1:],
            cwd=str(_REPO_ROOT),
        )

    async def list_descriptors_async(self) -> list[ToolDescriptor]:
        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                out: list[ToolDescriptor] = []
                for tool in listed.tools:
                    out.append(
                        ToolDescriptor(
                            id=f"mcp:{tool.name}",
                            name=tool.name,
                            provider="mcp",
                            source=self.server_label,
                            description=tool.description or "",
                            capabilities=["mcp.tools/call"],
                            input_schema=dict(
                                tool.input_schema.model_dump()
                                if hasattr(tool.input_schema, "model_dump")
                                else (tool.input_schema or {"type": "object"})
                            ),
                            output_schema=(
                                dict(tool.output_schema.model_dump())
                                if getattr(tool, "output_schema", None)
                                and hasattr(tool.output_schema, "model_dump")
                                else None
                            ),
                            permissions=["mcp:stdio"],
                            risk_level="low",
                            execution_mode="read",
                            availability="remote",
                            authentication="none",
                            cost="free",
                            status="experimental",
                            evidence=["mcp.tools/list"],
                        )
                    )
                return out

    def list_descriptors(self) -> list[ToolDescriptor]:
        return asyncio.run(self.list_descriptors_async())

    async def call_tool_async(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> ToolExecutionResult:
        started = time.perf_counter()
        tool_id = f"mcp:{tool_name}"
        try:
            async with stdio_client(self._stdio_params()) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments or {})
                    duration_ms = (time.perf_counter() - started) * 1000
                    is_error = bool(
                        getattr(result, "is_error", None)
                        or getattr(result, "isError", False)
                    )
                    text_parts = [
                        block.text
                        for block in result.content
                        if getattr(block, "text", None)
                    ]
                    structured = getattr(result, "structured_content", None) or getattr(
                        result, "structuredContent", None
                    )
                    payload: Any = {
                        "content": text_parts,
                        "structured_content": structured,
                        "is_error": is_error,
                    }
                    if is_error:
                        return ToolExecutionResult(
                            tool_id=tool_id,
                            provider="mcp",
                            ok=False,
                            result=payload,
                            error="mcp_tool_error",
                            duration_ms=duration_ms,
                        )
                    return ToolExecutionResult(
                        tool_id=tool_id,
                        provider="mcp",
                        ok=True,
                        result=payload,
                        duration_ms=duration_ms,
                    )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - started) * 1000
            return ToolExecutionResult(
                tool_id=tool_id,
                provider="mcp",
                ok=False,
                result=None,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=duration_ms,
            )

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> ToolExecutionResult:
        return asyncio.run(self.call_tool_async(tool_name, arguments))
