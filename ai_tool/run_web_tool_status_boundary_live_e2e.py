#!/usr/bin/env python3
"""Run Web Tool Status Boundary Live E2E Validation."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from ai_tool.web_tool_status_boundary_live_e2e import run_live_e2e_validation

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_status_boundary_live_e2e"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_STATUS_BOUNDARY_LIVE_E2E.md"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _write_doc(result: dict, run_id: str) -> None:
    lines = [
        "# Web Tool Status Boundary — Live E2E Validation",
        "",
        f"**Run:** `{run_id}`",
        f"**Git HEAD:** `{result.get('git_head')}`",
        f"**Live LLM:** `{result.get('live')}`",
        f"**HUMAN_INTERVENTION_COUNT:** `{result.get('human_intervention_count')}`",
        "",
        "## Summary",
        "",
        json.dumps(result.get("summary") or {}, ensure_ascii=False, indent=2),
        "",
        "## Findings",
        "",
        json.dumps(result.get("findings") or {}, ensure_ascii=False, indent=2),
        "",
        "## Production vs Eval",
        "",
        json.dumps(result.get("production_vs_eval") or {}, ensure_ascii=False, indent=2),
        "",
    ]
    for case in result.get("cases") or []:
        lines.append(f"### Case {case.get('case_id')} — {case.get('label')}")
        lines.append(f"- grade: **{case.get('grade')}** | observed: `{case.get('observed_overall')}` | expected: `{case.get('expected_overall')}`")
        mirror = case.get("production_mirror") or {}
        lines.append(f"- boundary_applied: {mirror.get('boundary_applied')}")
        lines.append(f"- user_visible_status: {mirror.get('user_visible_status')}")
        if mirror.get("raw_llm_answer"):
            lines.append(f"- raw_llm (excerpt): {str(mirror.get('raw_llm_answer'))[:200]}")
        if mirror.get("final_answer"):
            lines.append(f"- final_answer (excerpt): {str(mirror.get('final_answer'))[:200]}")
        lines.append("")
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Web Status Boundary Live E2E - starting ({RUN_ID})")

    ok, err = ollama_available()
    live = ok
    chat = None
    model = ""
    if live:
        import os

        prev = os.environ.get("AI_AGENT_MODEL")
        os.environ["AI_AGENT_MODEL"] = "qwen3_8b"
        import tools.system.llm as llm_mod

        llm_mod._client = None
        from tools.system.config import get_llm_profile

        model = str(get_llm_profile("qwen3_8b").get("model") or "")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None
    else:
        print(f"Ollama unavailable: {err} — mirror/subprocess live cases limited")

    result = run_live_e2e_validation(chat_fn=chat, model=model, live=live)
    result["run_id"] = RUN_ID
    result["git_head"] = _git_head()
    result["ollama_error"] = err if not live else None

    (RUN_DIR / "full_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_doc(result, RUN_ID)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_web_status.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/ai_tool/project_audit/test_web_tool_web_status_evaluation.py",
            "tests/ai_tool/project_audit/test_web_tool_status_boundary_live_e2e.py",
            "-q",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(json.dumps({"run_id": RUN_ID, "live": live, "summary": result["summary"], "pytest_exit": proc.returncode}, ensure_ascii=False))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
