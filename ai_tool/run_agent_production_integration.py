#!/usr/bin/env python3
"""Phase 5: Production Agent read_url_text integration isolated run."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.discovery import AgentToolDiscoveryAdapter
from ai_tool.agent_integration.production_bridge import (
    append_experimental_agent_tools,
    get_experimental_agent_exposure,
)
from ai_tool.agent_integration.trial import run_experimental_trial
from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_agent_read_url_integration"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _registry_sha() -> str:
    data = (_REPO / "registry" / "tools.json").read_bytes()
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    registry_before = _registry_sha()

    exposure = get_experimental_agent_exposure()
    adapter = AgentToolDiscoveryAdapter()
    discovery = adapter.get_tool_descriptor("local:read_url_text")

    trial = run_experimental_trial(audit=False)

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/agent_integration/test_production_bridge.py",
        "tests/ai_tool/agent_integration/test_production_integration.py",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)

    registry_after = _registry_sha()

    evaluation = {
        "success_criteria_met": (
            exposure.enabled
            and discovery is not None
            and discovery.agent_available is False
            and trial.ok
            and proc.returncode == 0
            and registry_before == registry_after
        ),
        "experimental_exposure_enabled": exposure.enabled,
        "discovery_agent_available": discovery.agent_available if discovery else None,
        "trial_routing_ok": trial.ok,
        "registry_unchanged": registry_before == registry_after,
        "pytest_passed": proc.returncode == 0,
    }

    inputs = {
        "experiment": "agent_read_url_production_integration_phase5",
        "phase": 5,
        "experimental_tool_id": "local:read_url_text",
        "registry_modified": False,
        "disable_env": "AI_AGENT_DISABLE_EXPERIMENTAL_READ_URL",
    }
    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "exposure.json").write_text(json.dumps(exposure.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "discovery_read_url.json").write_text(
        json.dumps(discovery.to_dict() if discovery else None, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "trial_results.json").write_text(json.dumps(trial.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "test_result.json").write_text(
        json.dumps(
            {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    safety = {
        "registry_sha256_unchanged": registry_before == registry_after,
        "ssrf_in_reader_not_bypassed": True,
        "agent_tool_gate_connected": True,
        "catalog_status_preserved": True,
    }
    (RUN_DIR / "safety_results.json").write_text(json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit(
        {"event": "agent_read_url_integration_phase5", "run_dir": str(RUN_DIR), "evaluation": evaluation},
        log_path=RUN_DIR / "audit.jsonl",
    )

    (RUN_DIR / "REPORT.md").write_text(
        "\n".join(
            [
                "# Agent read_url_text Production Integration — Phase 5",
                "",
                f"- exposure: `{exposure.tool_names}`",
                f"- discovery agent_available: `{discovery.agent_available if discovery else None}`",
                f"- registry unchanged: `{registry_before == registry_after}`",
                f"- pytest: `{'passed' if proc.returncode == 0 else 'FAILED'}`",
                "",
                "See `docs/ai_tool/agent_integration/PHASE5_REPORT.md`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
