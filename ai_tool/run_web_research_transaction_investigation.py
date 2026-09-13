#!/usr/bin/env python3
"""Run Web Research Transaction Investigation."""
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
from ai_tool.web_research_transaction_investigation import run_investigation
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_research_transaction_investigation"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
PROFILE = "qwen3_8b"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Web Research Transaction Investigation - starting ({RUN_ID})")

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

    result = run_investigation(fetch_live=True, llm_enabled=llm_enabled, chat_fn=chat, model=model)
    result["run_id"] = RUN_ID

    (RUN_DIR / "observations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "extraction_results.json").write_text(
        json.dumps(result.get("investigation_a_extraction") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "golden_transactions.json").write_text(
        json.dumps(result.get("investigation_d_golden_transactions") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "comparisons.json").write_text(
        json.dumps(
            {
                "orchestration": result.get("investigation_b_orchestration"),
                "architecture_options": result.get("architecture_options"),
                "llm_boundary": result.get("investigation_llm_boundary"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "diagnosis.json").write_text(
        json.dumps(
            {
                "recommendation": result.get("recommendation"),
                "unknowns": result.get("unknowns"),
                "human_review_packet": result.get("human_review_packet"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "architecture_options.json").write_text(
        json.dumps(result.get("architecture_options") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "recommendation.json").write_text(
        json.dumps(result.get("recommendation") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "stop": result.get("stop"),
                "next_phase": result.get("next_phase_proposal"),
                "selected_architecture": (result.get("recommendation") or {}).get("selected"),
                "git_commit": False,
                "production_changes": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (RUN_DIR / "human_review_packet.json").write_text(
        json.dumps(result.get("human_review_packet") or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_research_transaction_investigation.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(json.dumps({"run_id": RUN_ID, "llm_enabled": llm_enabled, "pytest_exit": proc.returncode}, indent=2))
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
