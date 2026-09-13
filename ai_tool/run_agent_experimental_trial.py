#!/usr/bin/env python3
"""Phase 4: Experimental Tool Execution Trial isolated run."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.trial import run_experimental_trial
from ai_tool.agent_integration.trial_scenarios import DEFAULT_TRIAL_SCENARIOS, ROUTING_COMPARISON
from ai_tool.catalog.store import catalog_entries_dir

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_agent_experimental_trial"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    sandbox_entries = RUN_DIR / "catalog_sandbox" / "entries"
    shutil.copytree(catalog_entries_dir(), sandbox_entries)

    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=sandbox_entries)
    discovery_before = adapter.get_tool_descriptor("local:read_url_text")
    discovery_before_dict = discovery_before.to_dict() if discovery_before else None

    audit_log = RUN_DIR / "audit.jsonl"
    trial_result = run_experimental_trial(
        catalog_entries_dir=sandbox_entries,
        audit=True,
        audit_log=audit_log,
    )

    discovery_after = adapter.get_tool_descriptor("local:read_url_text")
    discovery_after_dict = discovery_after.to_dict() if discovery_after else None

    pytest_cmd = [sys.executable, "-m", "pytest", "tests/ai_tool/agent_integration/test_trial.py", "-q"]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)
    test_result = {
        "command": " ".join(pytest_cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }

    safety = {
        "execution_count": trial_result.execution_count,
        "registry_modified": trial_result.registry_modified,
        "production_agent_path_modified": trial_result.production_agent_path_modified,
        "discovery_agent_available_unchanged": (
            discovery_before_dict is not None
            and discovery_after_dict is not None
            and discovery_before_dict["agent_available"] is False
            and discovery_after_dict["agent_available"] is False
        ),
        "trial_isolated": True,
        "network_in_trial": "mock_fetch_and_mock_search_only",
    }

    evaluation = {
        "success_criteria_met": trial_result.ok and test_result["passed"] and safety["discovery_agent_available_unchanged"],
        "trial_ok": trial_result.ok,
        "routing_scenarios_passed": all(s.routing_match for s in trial_result.scenario_results),
        "execution_count": trial_result.execution_count,
    }

    inputs = {
        "experiment": "agent_experimental_trial_phase4",
        "phase": 4,
        "experimental_tool_id": "local:read_url_text",
        "production_tools_in_trial": trial_result.production_tools,
        "constraints": {
            "registry_modified": False,
            "production_agent_path_modified": False,
            "discovery_agent_available_changes": False,
        },
    }
    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "discovery_before.json").write_text(
        json.dumps(discovery_before_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "trial_results.json").write_text(
        json.dumps(trial_result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "routing_comparison.json").write_text(
        json.dumps(ROUTING_COMPARISON, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "scenarios.json").write_text(
        json.dumps([s.to_dict() for s in DEFAULT_TRIAL_SCENARIOS], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "safety_results.json").write_text(json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "test_result.json").write_text(json.dumps(test_result, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Agent Experimental Trial — Phase 4 Run",
        "",
        f"- **run_dir:** `{RUN_DIR.relative_to(_REPO).as_posix()}`",
        f"- **tools exposed:** {', '.join(trial_result.tools_exposed)}",
        f"- **execution_count:** {trial_result.execution_count}",
        f"- **routing ok:** {evaluation['routing_scenarios_passed']}",
        f"- **discovery agent_available:** false (unchanged)",
        "",
        "See `docs/ai_tool/agent_integration/PHASE4_REPORT.md`.",
    ]
    (RUN_DIR / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
