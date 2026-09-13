"""Local LLM pre-run failure prediction for long E2E checkpoints."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_tool.dev_skill_pipeline import load_registry
from ai_tool.llm_json_parse import llm_response_diagnostics, message_content
from tools.system.llm import chat as llm_chat

TETRIS_PRD: dict[str, Any] = {
    "title": "Dedicated Sandbox 最小テトリス",
    "problem": "Minimal console Tetris in Dedicated Sandbox.",
    "goals": "Single-file Python console Tetris.",
    "requirements": "tetris/main.py with core loop, line clear, score.",
    "non_goals": "GUI, network, production writes.",
    "constraints": "Dedicated Sandbox only.",
    "acceptance_criteria": ["tetris/main.py exists", "python runnable"],
    "recommended_answer": "approve",
}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _thinking_probe(model: str) -> dict[str, Any]:
    registry = load_registry()
    system = (
        "Respond ONLY with JSON: {\"status\":\"ok\"}."
    )
    user = "Emit the JSON object now."
    default_resp = chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format="json",
    )
    mitigated_resp = chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        format="json",
        execution_profile="structured_output",
    )
    default_diag = llm_response_diagnostics(default_resp)
    mitigated_diag = llm_response_diagnostics(mitigated_resp)
    return {
        "default_think": {
            **default_diag,
            "usable_content": bool(message_content(default_resp).strip()),
        },
        "think_false": {
            **mitigated_diag,
            "usable_content": bool(message_content(mitigated_resp).strip()),
        },
    }


def chat(**kwargs: Any) -> Any:
    return llm_chat(**kwargs)


def run_prefault_prediction(
    *,
    run_dir: Path,
    model: str,
    composition_id: str = "tetris-sandbox-e2e",
) -> dict[str, Any]:
    """Predict likely E2E blockers with local probes and one structured LLM forecast."""
    probe = _thinking_probe(model)
    default_risk = (
        not probe["default_think"]["usable_content"]
        and int(probe["default_think"].get("thinking_len") or 0) > 0
        and probe["default_think"].get("done_reason") == "length"
    )
    predicted_blockers: list[dict[str, Any]] = []
    if default_risk:
        predicted_blockers.append(
            {
                "id": "thinking_budget_exhaustion",
                "skill_id": "tech-spec",
                "symptom": "empty message.content with done_reason=length",
                "likelihood": "high",
                "mitigation": "execution_profile=structured_output (think=false)",
            }
        )

    forecast_user = (
        f"Composition: {composition_id}\n"
        f"Model: {model}\n"
        f"Probe: {json.dumps(probe, ensure_ascii=False)}\n\n"
        "Predict the top failure risks for this Dev Skill + Production Chat Tetris E2E. "
        "Emit JSON with keys: predicted_blockers (array of {id,skill_id,symptom,likelihood}), "
        "recommended_preflight_checks (array of strings), confidence (low|medium|high)."
    )
    forecast: dict[str, Any] = {"parse_status": "skipped"}
    try:
        forecast_resp = chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You forecast E2E failure risks. Respond ONLY with JSON.",
                },
                {"role": "user", "content": forecast_user},
            ],
            format="json",
            execution_profile="deep_reasoning",
        )
        raw = message_content(forecast_resp)
        forecast = {
            "parse_status": "ok" if raw.strip() else "empty",
            "payload": json.loads(raw) if raw.strip() else None,
            "diagnostics": llm_response_diagnostics(forecast_resp),
        }
    except Exception as exc:  # noqa: BLE001
        forecast = {"parse_status": "error", "error": f"{type(exc).__name__}: {exc}"}

    prediction = {
        "generated_at": _utc_stamp(),
        "model": model,
        "composition_id": composition_id,
        "probe": probe,
        "predicted_blockers": predicted_blockers,
        "llm_forecast": forecast,
        "mitigations_applied_before_e2e": ["execution_profile_structured_output_for_json_harness"],
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "prefault_prediction.json"
    out_path.write_text(json.dumps(prediction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return prediction


__all__ = ["run_prefault_prediction"]
