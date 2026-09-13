#!/usr/bin/env python3
"""Phase 3: Human Review → Catalog status update isolated run."""
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
from ai_tool.catalog.review import apply_human_review
from ai_tool.catalog.store import catalog_entries_dir
from ai_tool.core.audit import append_audit

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_human_review"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID


def _status_snapshot(entries_dir: Path, tool_id: str) -> dict | None:
    adapter = AgentToolDiscoveryAdapter(catalog_entries_dir=entries_dir)
    tool = adapter.get_tool_descriptor(tool_id)
    if tool is None:
        return None
    return {
        "tool_id": tool.tool_id,
        "source": tool.source,
        "discovery_category": tool.discovery_category,
        "agent_available": tool.agent_available,
        "catalog_status": tool.catalog_status.to_dict(),
        "unavailability_reason": tool.unavailability_reason,
    }


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    sandbox_entries = RUN_DIR / "catalog_sandbox" / "entries"
    shutil.copytree(catalog_entries_dir(), sandbox_entries)

    tool_id = "local:read_url_text"
    reviews_log = RUN_DIR / "reviews.jsonl"
    audit_log = RUN_DIR / "audit.jsonl"

    before = _status_snapshot(sandbox_entries, tool_id)
    review_action = apply_human_review(
        tool_id,
        "approved",
        reason="phase3 isolated run — adoption judgment only",
        notes="does not grant agent execution",
        entries_dir=sandbox_entries,
        reviews_log=reviews_log,
        audit_log=audit_log,
    )
    after = _status_snapshot(sandbox_entries, tool_id)

    pytest_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/ai_tool/agent_integration/test_human_review.py",
        "-q",
    ]
    proc = subprocess.run(pytest_cmd, cwd=_REPO, capture_output=True, text=True)
    test_result = {
        "command": " ".join(pytest_cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }

    safety = {
        "execution_count": review_action.execution_count,
        "catalog_metadata_only": True,
        "production_catalog_modified": False,
        "registry_modified": False,
        "network_access": False,
        "mcp_call": False,
        "tool_execution_during_review": False,
        "agent_available_after_approved": review_action.agent_available,
    }

    evaluation = {
        "success_criteria_met": (
            review_action.ok
            and review_action.agent_available is False
            and after is not None
            and after["catalog_status"]["adoption_status"] == "approved"
            and after["catalog_status"]["tool_status"] == "unavailable"
            and after["agent_available"] is False
            and test_result["passed"]
        ),
        "review_ok": review_action.ok,
        "agent_available_unchanged": review_action.agent_available is False,
        "adoption_status_after": after["catalog_status"]["adoption_status"] if after else None,
    }

    inputs = {
        "experiment": "human_review_phase3",
        "phase": 3,
        "tool_id": tool_id,
        "review_status": "approved",
        "sandbox_entries": str(sandbox_entries.relative_to(_REPO)),
        "constraints": {
            "registry_modified": False,
            "agent_execution_enabled": False,
            "llm_exposure": False,
        },
    }
    (RUN_DIR / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "review_before.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "review_action.json").write_text(
        json.dumps(review_action.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "review_after.json").write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "safety_results.json").write_text(json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "test_result.json").write_text(json.dumps(test_result, ensure_ascii=False, indent=2), encoding="utf-8")

    append_audit(
        {
            "event": "human_review_phase3_run",
            "run_dir": str(RUN_DIR),
            "tool_id": tool_id,
            "execution_count": 0,
        },
        log_path=RUN_DIR / "audit.jsonl",
    )

    report = [
        "# Human Review — Phase 3 Run",
        "",
        f"- **run_dir:** `{RUN_DIR.relative_to(_REPO).as_posix()}`",
        f"- **tool_id:** `{tool_id}`",
        f"- **review:** not_reviewed → approved (sandbox only)",
        f"- **agent_available after review:** {after['agent_available'] if after else 'UNKNOWN'}",
        f"- **pytest:** {'passed' if test_result['passed'] else 'FAILED'}",
        "",
        "See `docs/ai_tool/agent_integration/PHASE3_REPORT.md`.",
    ]
    (RUN_DIR / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"run_dir": str(RUN_DIR), "evaluation": evaluation}, ensure_ascii=False, indent=2))
    return 0 if evaluation["success_criteria_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
