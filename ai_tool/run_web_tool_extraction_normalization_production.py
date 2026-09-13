#!/usr/bin/env python3
"""Run Production Extraction Normalization validation."""
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
from ai_tool.web_tool_extraction_normalization_production import run_validation
from tools.system.config import get_llm_profile

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_extraction_normalization_production"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
PROFILE = "qwen3_8b"

BASELINE = {
    "GT1": {"grade": "FAIL"},
    "GT2": {"grade": "PASS"},
    "GT3": {"grade": "PASS"},
    "GT4": {"grade": "FAIL"},
    "GT5": {"grade": "FAIL"},
    "GT6": {"grade": "PASS"},
}


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Production Extraction Normalization - starting ({RUN_ID})")

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

    result = run_validation(
        fetch_live=True,
        baseline=BASELINE,
        llm_enabled=llm_enabled,
        chat_fn=chat,
        model=model,
    )
    result["run_id"] = RUN_ID

    (RUN_DIR / "baseline.json").write_text(json.dumps(BASELINE, indent=2), encoding="utf-8")
    (RUN_DIR / "observations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUN_DIR / "before_after.json").write_text(
        json.dumps(result.get("before_after") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RUN_DIR / "decision.json").write_text(
        json.dumps(
            {
                "overall": result.get("overall"),
                "stop": result.get("stop"),
                "golden_overall": (result.get("golden_production") or {}).get("overall"),
                "human_review_required": result.get("human_review_required"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/ai_tool/experimental/test_read_url_evidence.py",
            "tests/ai_tool/experimental/test_html_normalize_paragraph_density.py",
            "tests/test_web_evidence_pipeline.py",
            "tests/test_web_status.py",
            "-q",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall": result.get("overall"),
                "golden": (result.get("golden_production") or {}).get("overall"),
                "pytest_exit": proc.returncode,
            },
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 and result.get("stop") else 1


if __name__ == "__main__":
    sys.exit(main())
