#!/usr/bin/env python3
"""Run Web Tool End-to-End Practical Evaluation Phase 3."""
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
from ai_tool.web_tool_end_to_end_evaluation_phase3 import run_end_to_end_evaluation
from tools.system.config import get_llm_profile
from tools.system.llm_tool_capability import probe_tool_calling

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S") + "_web_tool_end_to_end_evaluation_phase3"
RUN_DIR = _REPO / "runs" / "ai_tool" / RUN_ID
DOC_PATH = _REPO / "docs" / "ai_tool" / "project_audit" / "WEB_TOOL_END_TO_END_EVALUATION_PHASE3.md"
PROFILE = "qwen3_8b"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=_REPO).strip()
    except Exception:
        return "UNKNOWN"


def _reset_llm_client() -> None:
    import tools.system.llm as llm_mod

    llm_mod._client = None
    llm_mod._client_timeout = None


def _write_doc(evaluation: dict, run_id: str) -> None:
    lines = [
        "# Web Tool End-to-End Practical Evaluation — Phase 3",
        "",
        f"**Run:** `{run_id}`",
        f"**Git HEAD:** `{evaluation.get('git_head')}`",
        f"**Overall live E2E:** {evaluation.get('overall_live_e2e')}",
        f"**Overall tool-only:** {evaluation.get('overall_tool_only')}",
        "",
        "## Findings",
        "",
        json.dumps(evaluation.get("findings") or {}, ensure_ascii=False, indent=2),
        "",
        "## Proposals",
        "",
        json.dumps(evaluation.get("proposals") or [], ensure_ascii=False, indent=2),
        "",
        "## Live cases",
        "",
    ]
    for case in evaluation.get("live_lane") or []:
        lines.append(f"### Case {case.get('case_id')} — E2E {case.get('overall')}")
        lines.append(json.dumps(case.get("e2e_stages") or {}, ensure_ascii=False, indent=2))
        lines.append("")
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    obs_dir = RUN_DIR / "observations"
    trace_dir = RUN_DIR / "traces"
    diag_dir = RUN_DIR / "diagnosis"
    prop_dir = RUN_DIR / "proposals"
    for d in (obs_dir, trace_dir, diag_dir, prop_dir):
        d.mkdir(parents=True, exist_ok=True)

    print(f"Web Tool E2E Evaluation Phase 3 - starting ({RUN_ID})")

    ok, err = ollama_available()
    live_enabled = ok
    chat = None
    model = ""
    cap: dict = {"supported": False}

    if live_enabled:
        prev = os.environ.get("AI_AGENT_MODEL")
        os.environ["AI_AGENT_MODEL"] = PROFILE
        _reset_llm_client()
        profile = get_llm_profile(PROFILE)
        model = str(profile.get("model") or "")
        chat = live_chat_fn()
        cap = probe_tool_calling(model, chat_fn=chat)
        live_enabled = cap.get("supported") is True
        if prev is None:
            os.environ.pop("AI_AGENT_MODEL", None)
        else:
            os.environ["AI_AGENT_MODEL"] = prev
        _reset_llm_client()

    evaluation = run_end_to_end_evaluation(chat_fn=chat, model=model, live_enabled=live_enabled)
    evaluation["run_id"] = RUN_ID
    evaluation["git_head"] = _git_head()
    evaluation["capability"] = cap
    evaluation["live_enabled"] = live_enabled

    (RUN_DIR / "evaluation.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    (obs_dir / "tool_only.json").write_text(
        json.dumps(evaluation["tool_only_lane"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (obs_dir / "live.json").write_text(
        json.dumps(evaluation["live_lane"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (diag_dir / "findings.json").write_text(
        json.dumps(evaluation["findings"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (prop_dir / "next_iteration.json").write_text(
        json.dumps(evaluation["proposals"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for case in evaluation.get("live_lane") or []:
        cid = case.get("case_id")
        if cid:
            (trace_dir / f"case_{cid}_live.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai_tool/project_audit/test_web_tool_end_to_end_evaluation_phase3.py", "-q"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    (RUN_DIR / "pytest.txt").write_text(proc.stdout + proc.stderr, encoding="utf-8")

    _write_doc(evaluation, RUN_ID)
    print(
        json.dumps(
            {
                "run_id": RUN_ID,
                "overall_live_e2e": evaluation.get("overall_live_e2e"),
                "overall_tool_only": evaluation.get("overall_tool_only"),
                "live_enabled": live_enabled,
                "pytest_exit": proc.returncode,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Artifacts: {RUN_DIR}")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
