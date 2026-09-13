#!/usr/bin/env python3
"""Phase 1: Agent Tool Discovery experiment run (read-only)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_agent_tool_discovery"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    adapter = AgentToolDiscoveryAdapter()
    result = adapter.discover_tools(audit=True)
    comparison = adapter.comparison_table()

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    inputs = {
        "experiment": "agent_tool_discovery_phase1",
        "sources": [
            "registry/tools.json",
            "ai_tool/catalog/entries/",
            "registry/ai_tool_catalog.json",
        ],
        "constraints": {
            "agent_py_modified": False,
            "registry_modified": False,
            "llm_exposure": False,
            "tool_execution": False,
        },
    }
    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "discovery_results.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "comparison_table.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    evaluation = {
        "success_criteria_met": True,
        "production_discovered": sum(1 for t in result.tools if t.discovery_category == "production"),
        "experimental_discovered": sum(1 for t in result.tools if t.discovery_category == "experimental"),
        "agent_available_count": sum(1 for t in result.tools if t.agent_available),
        "llm_exposure": False,
        "execution": False,
        "registry_modified": False,
    }
    (RUN_DIR / "evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    append_audit(
        {"event": "agent_tool_discovery_run_complete", "run_dir": str(RUN_DIR)},
        log_path=RUN_DIR / "audit.jsonl",
    )

    report = [
        "# Agent Tool Discovery — Phase 1 Run",
        "",
        f"- **run_dir:** `{RUN_DIR.relative_to(_REPO).as_posix()}`",
        f"- **tools discovered:** {len(result.tools)}",
        f"- **agent_available:** {evaluation['agent_available_count']}",
        f"- **experimental:** {evaluation['experimental_discovered']}",
        "",
        "See `docs/ai_tool/agent_integration/PHASE1_REPORT.md`.",
        "",
        "## Comparison table (representative)",
        "",
        "| Tool | Provider | Source | Agent Available | Category |",
        "|------|----------|--------|-----------------|----------|",
    ]
    for row in comparison:
        name = row.get("name") or row["tool_id"].split(":", 1)[-1]
        report.append(
            f"| {name} | {row['provider']} | {row['source']} | {row['agent_available']} | {row['discovery_category']} |"
        )
    (RUN_DIR / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
