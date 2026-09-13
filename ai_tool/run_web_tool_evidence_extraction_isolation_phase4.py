#!/usr/bin/env python3
"""Run Web Tool Evidence Extraction Isolation Phase 4."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.agent_integration.gpu_process_e2e import live_chat_fn, ollama_available
from ai_tool.web_tool_evidence_extraction_isolation_phase4 import run_evidence_extraction_isolation
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_evidence_extraction_isolation_phase4"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
PROFILE = "qwen3_8b"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _write_run_summary(result: dict, run_id: str, run_dir: Path) -> None:
    lines = [
        f"# Run Summary — {run_id}",
        "",
        f"**Git HEAD:** `{result.get('git_head')}`",
        "",
        "## Findings",
        "",
        json.dumps(result.get("findings") or {}, ensure_ascii=False, indent=2),
        "",
        "## Success Criteria",
        "",
        json.dumps(result.get("success_criteria") or {}, ensure_ascii=False, indent=2),
    ]
    (run_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Evidence Extraction Isolation Phase 4 - starting ({RUN_ID})")

    ok, _ = ollama_available()
    llm_enabled = ok
    chat = None
    model = ""
    if llm_enabled:
        prev = os.environ.get("AI_AGENT_MODEL")
        os.environ["AI_AGENT_MODEL"] = PROFILE
        import tools.system.llm as llm_mod

        llm_mod._client = None
        profile = get_llm_profile(PROFILE)
        model = str(profile.get("model") or "")
        chat = live_chat_fn()
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        llm_mod._client = None

    result = run_evidence_extraction_isolation(chat_fn=chat, model=model, llm_enabled=llm_enabled)
    result["run_id"] = RUN_ID
    result["git_head"] = _git_head()
    result["llm_enabled"] = llm_enabled

    (RUN_DIR / "cases.json").write_text(json.dumps(result["cases"], ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "findings.json").write_text(json.dumps(result["findings"], ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "proposals.json").write_text(json.dumps(result["proposals"], ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "byte_sweep_e2.json").write_text(json.dumps(result["byte_sweep_e2"], ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "full_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_tool_evidence_extraction_isolation_phase4.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    _write_run_summary(result, RUN_ID, RUN_DIR)
    print(json.dumps({"run_id": RUN_ID, "llm_enabled": llm_enabled, "pytest_exit": proc.returncode}, ensure_ascii=False, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
