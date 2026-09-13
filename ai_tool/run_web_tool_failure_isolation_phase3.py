#!/usr/bin/env python3
"""Run Web Tool Failure Isolation Phase 3 (read-only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.web_tool_failure_isolation_phase3 import domain_status, run_failure_isolation

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_failure_isolation_phase3"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_FAILURE_ISOLATION_PHASE3.md"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _write_doc(analysis: dict[str, Any], domains: dict, run_id: str) -> None:
    lines = [
        "# Web Tool Failure Isolation — Phase 3",
        "",
        f"**Run:** `{run_id}`",
        f"**Git HEAD:** `{_git_head()}`",
        "**Production changes:** NONE",
        "",
        "## Domain status",
        "",
        json.dumps(domains, ensure_ascii=False, indent=2),
        "",
        "## Root cause table",
        "",
        "| Problem | Layer | Confidence | Impact | Next action |",
        "|---------|-------|------------|--------|-------------|",
    ]
    for row in analysis.get("root_cause_table") or []:
        lines.append(
            f"| {row.get('problem')} | {row.get('layer')} | {row.get('confidence')} | "
            f"{row.get('impact')} | {row.get('proposed_next_action')} |"
        )
    lines.extend(["", "## Proposed options", ""])
    for key, opt in (analysis.get("proposed_options") or {}).items():
        lines.append(f"### {key}: {opt.get('title')}")
        lines.append(json.dumps(opt, ensure_ascii=False, indent=2))
        lines.append("")
    lines.extend(["", "## Automation loop insights", ""])
    lines.append(json.dumps(analysis.get("automation_loop_insights") or [], ensure_ascii=False, indent=2))
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Web Tool Failure Isolation Phase 3 - starting ({RUN_ID})")
    analysis = run_failure_isolation()
    analysis["run_id"] = RUN_ID
    analysis["git_head"] = _git_head()
    domains = domain_status(analysis)
    analysis["domain_status"] = domains

    (RUN_DIR / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "search_isolation.json").write_text(
        json.dumps(analysis["search_isolation"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "agent_loop.json").write_text(
        json.dumps(analysis["agent_loop"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (RUN_DIR / "root_cause_table.json").write_text(
        json.dumps(analysis["root_cause_table"], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _write_doc(analysis, domains, RUN_ID)
    (RUN_DIR / "domain_status.json").write_text(json.dumps(domains, ensure_ascii=False, indent=2), encoding="utf-8")

    # pytest record
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_tool_failure_isolation_phase3.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest_output.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(json.dumps({"run_id": RUN_ID, "domains": domains, "pytest_exit": proc.returncode}, ensure_ascii=False, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
