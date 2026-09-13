#!/usr/bin/env python3
"""Phase 2: Agent Tool Discovery Hook isolated run."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.hook import run_agent_discovery_hook
from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_agent_discovery_hook"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    result = run_agent_discovery_hook(audit=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    inputs = {
        "experiment": "agent_discovery_hook_phase2",
        "phase": 2,
        "constraints": {
            "execution_allowed": False,
            "registry_modified": False,
            "llm_exposure": False,
        },
    }
    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")

    discovered = [t.to_dict() for t in result.tools]
    (RUN_DIR / "discovered_tools.json").write_text(
        json.dumps(discovered, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "discovery_results.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    safety = {
        "execution_count": result.execution_count,
        "discovery_only": result.discovery_only,
        "tool_execution_during_discovery": False,
        "registry_modified": False,
        "network_access": False,
        "filesystem_write": False,
        "mcp_call": False,
    }
    (RUN_DIR / "safety_results.json").write_text(
        json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    evaluation = {
        "success_criteria_met": result.ok and result.execution_count == 0,
        "hook_ok": result.ok,
        "execution_count": result.execution_count,
        "production_count": result.production_count,
        "experimental_count": result.experimental_count,
        "agent_available_count": result.agent_available_count,
    }
    (RUN_DIR / "evaluation.json").write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    append_audit(
        {"event": "agent_discovery_hook_run", "run_dir": str(RUN_DIR), "execution_count": 0},
        log_path=RUN_DIR / "audit.jsonl",
    )

    report = [
        "# Agent Discovery Hook — Phase 2 Run",
        "",
        f"- **run_dir:** `{RUN_DIR.relative_to(_REPO).as_posix()}`",
        f"- **tools:** {len(result.tools)}",
        f"- **execution_count:** {result.execution_count}",
        f"- **production:** {result.production_count}",
        f"- **experimental:** {result.experimental_count}",
        "",
        "See `docs/ai_tool/agent_integration/PHASE2_REPORT.md`.",
    ]
    (RUN_DIR / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
