#!/usr/bin/env python3
"""Phase 1 experiment: local vs MCP get_current_time comparison."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.core.audit import append_audit
from ai_tool.core.safety import evaluate_tool_safety
from ai_tool.providers.local.provider import local_get_current_time
from ai_tool.providers.mcp.provider import MCPToolProvider
from ai_tool.registry.catalog import ToolCatalog

RUN_DIR = _REPO / "runs" / "ai_tool" / "20260828_140000_local_vs_mcp_time"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    catalog = ToolCatalog()
    audit_id = catalog.audit_discovery()

    local_desc = next(
        (d for d in catalog.list_all_descriptors(include_mcp_live=False) if d.name == "cpu_status"),
        None,
    )
    mcp_desc = next(
        (d for d in catalog.load_manual_entries() if d.get("name") == "get_current_time"),
        None,
    )

    # A: local reference time (not registry — parity function for MCP time tool)
    t0 = time.perf_counter()
    local_time = local_get_current_time()
    local_ms = (time.perf_counter() - t0) * 1000

    # B: MCP get_current_time
    mcp = MCPToolProvider()
    mcp_result = mcp.call_tool("get_current_time", {})
    mcp_list = mcp.list_descriptors()

    local_safety = evaluate_tool_safety(
        catalog.local.get_descriptor("local:cpu_status")  # type: ignore[arg-type]
        or catalog.local.list_descriptors()[0]
    )
    from ai_tool.core.models import ToolDescriptor

    mcp_td = ToolDescriptor(**mcp_desc) if mcp_desc else mcp.list_descriptors()[0]
    mcp_safety = evaluate_tool_safety(mcp_td)

    comparison = {
        "experiment": "EXP-001_local_vs_mcp_time",
        "audit_id": audit_id,
        "local_reference": {
            "kind": "local_get_current_time",
            "result": local_time,
            "duration_ms": round(local_ms, 3),
            "safety": local_safety.to_dict(),
        },
        "mcp": {
            "tool": "get_current_time",
            "list_count": len(mcp_list),
            "result": mcp_result.to_dict(),
            "safety": mcp_safety.to_dict(),
        },
        "registry_local_agent_tools": len(catalog.local.list_descriptors(visibility="agent")),
        "catalog_total": len(catalog.list_all_descriptors(include_mcp_live=True)),
        "agent_view_sample": catalog.summarize_for_agent_view()[:3],
    }

    out_json = RUN_DIR / "results.json"
    out_json.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit(
        {
            "event": "experiment_complete",
            "experiment": "EXP-001",
            "run_dir": str(RUN_DIR),
            "mcp_ok": mcp_result.ok,
        }
    )

    report = RUN_DIR / "EXPERIMENT_REPORT.md"
    report.write_text(
        "\n".join(
            [
                "# EXP-001 — Local vs MCP get_current_time",
                "",
                f"- **audit_id:** {audit_id}",
                f"- **mcp_ok:** {mcp_result.ok}",
                f"- **local_duration_ms:** {local_ms:.3f}",
                f"- **mcp_duration_ms:** {mcp_result.duration_ms}",
                "",
                "## Verdict",
                "",
                "| Area | Status |",
                "|------|--------|",
                "| Common Tool Model | EXPERIMENTAL |",
                "| Local Provider | ADOPT CANDIDATE (read registry) |",
                "| MCP Provider | EXPERIMENTAL (1 read-only tool) |",
                "| Agent integration | NOT READY (catalog only) |",
                "| Registry merge | NOT READY (manual catalog) |",
                "",
                f"Results: `{out_json.relative_to(_REPO)}`",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0 if mcp_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
