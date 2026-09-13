"""Minimal read-only MCP server exposing get_current_time (stdio)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("ai-tool-time-server", version="0.1.0")


@mcp.tool()
def get_current_time() -> str:
    """Return current UTC time as ISO8601 string (read-only)."""
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
