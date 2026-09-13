#!/usr/bin/env python3
"""Diagnose tech-spec LLM response pipeline stages (reproduction harness)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ai_tool.dev_skill_pipeline import (
    _message_content,
    _skill_system,
    _strip_json_fence,
    load_registry,
    parse_json_content,
)
from tools.system.config import get_llm_profile
from tools.system.llm import chat as llm_chat

TETRIS_PRD: dict[str, Any] = {
    "title": "Dedicated Sandbox 最小テトリス",
    "problem": "The user wants a minimal, playable Tetris game in a console environment within a specific sandbox.",
    "goals": "Create a functional, single-file Python console Tetris game that includes core mechanics.",
    "requirements": (
        "['Implement the entire game in a single file: tetris/main.py.', "
        "'Include a core game loop handling piece movement and gravity.', "
        "'Implement line clearing logic.', "
        "'Include a scoring system.', "
        "'Provide clear instructions on how to run the game.']"
    ),
    "non_goals": (
        "['GUI-based graphics (e.g., Pygame).', "
        "'Network multiplayer functionality.', "
        "'Modifying any files outside the tetris/ directory.']"
    ),
    "constraints": (
        "['Must be a standalone Python script.', "
        "'Must be located in the tetris/ directory within the Sandbox.']"
    ),
    "acceptance_criteria": [
        "tetris/main.py exists in the sandbox.",
        "The game is runnable via a single command.",
        "Core mechanics (falling, clearing, scoring) are functional.",
    ],
    "recommended_answer": "approve",
}


def _response_fields(response: Any) -> dict[str, Any]:
    msg = getattr(response, "message", None)
    content = str(getattr(msg, "content", None) or "")
    thinking = str(getattr(msg, "thinking", None) or "")
    dumped: dict[str, Any] = {}
    if hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump()
        except Exception:  # noqa: BLE001
            dumped = {}
    return {
        "content_len": len(content),
        "thinking_len": len(thinking),
        "content_preview": content[:400],
        "thinking_preview": thinking[:400],
        "message_content_len": len(_message_content(response)),
        "eval_count": dumped.get("eval_count"),
        "prompt_eval_count": dumped.get("prompt_eval_count"),
        "done": dumped.get("done"),
        "done_reason": dumped.get("done_reason"),
    }


def diagnose_call(
    label: str,
    system: str,
    user: str,
    model: str,
    *,
    think: bool | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "label": label,
        "system_chars": len(system),
        "user_chars": len(user),
        "total_prompt_chars": len(system) + len(user),
    }
    started = time.perf_counter()
    chat_kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": "json",
    }
    if think is False:
        chat_kwargs["execution_profile"] = "structured_output"
    elif think is True:
        chat_kwargs["execution_profile"] = "human_intent"
    row["think"] = think
    try:
        response = llm_chat(**chat_kwargs)
    except Exception as exc:  # noqa: BLE001
        row["stage"] = "llm_call"
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        return row

    row["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    row["raw"] = _response_fields(response)

    raw_text = _message_content(response)
    row["normalized_len"] = len(raw_text.strip())
    extracted = _strip_json_fence(raw_text)
    row["extracted_len"] = len(extracted)
    row["extracted_preview"] = extracted[:400]

    if not extracted.strip():
        row["stage"] = "json_extraction"
        row["failure"] = "empty_after_extraction"
        return row

    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        row["stage"] = "json_loads"
        row["failure"] = f"JSONDecodeError: {exc}"
        return row

    if not isinstance(payload, dict):
        row["stage"] = "schema_validation"
        row["failure"] = "root_not_object"
        return row

    row["stage"] = "ok"
    row["keys"] = sorted(payload.keys())
    return row


def main() -> int:
    registry = load_registry()
    model = str(get_llm_profile().get("model") or "")
    write_prd_system = (
        _skill_system("write-prd", registry)
        + "\n\nHarness policy: run Phase 4 only in a single response."
    )
    write_prd_user = (
        "Initial request:\nテトリスを作って\n\n"
        "Emit PRD_JSON with keys: title, problem, goals, requirements, non_goals, "
        "constraints, acceptance_criteria (array), recommended_answer."
    )
    tech_spec_system = (
        _skill_system("tech-spec", registry)
        + "\n\nHarness policy: skip Phase 6 grill-me gate. Single TECH_SPEC_JSON response only."
    )
    tech_spec_user = (
        f"PRD JSON:\n{json.dumps(TETRIS_PRD, ensure_ascii=False, indent=2)}\n\n"
        "For this E2E, implementation target is Dedicated Sandbox via Production Chat "
        "create_file only. Emit TECH_SPEC_JSON with keys: summary, modules, sequencing, "
        "sandbox_constraints, implementation_tasks (array of {id,title,acceptance,size}), "
        "recommended_answer."
    )

    report = {
        "model": model,
        "calls": [
            diagnose_call("write-prd-default", write_prd_system, write_prd_user, model),
            diagnose_call("tech-spec-default", tech_spec_system, tech_spec_user, model),
            diagnose_call(
                "tech-spec-think-false",
                tech_spec_system,
                tech_spec_user,
                model,
                think=False,
            ),
        ],
    }
    out_dir = _REPO / "logs" / "_tech_spec_diagnose"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "diagnose_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"wrote {out_path}")
    failed = [row for row in report["calls"] if row.get("stage") != "ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
