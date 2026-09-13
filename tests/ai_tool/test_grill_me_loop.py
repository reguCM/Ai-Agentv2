from __future__ import annotations

import pytest

from ai_tool.grill_me_loop import (
    TETRIS_FALLBACK_SPEC,
    build_implementation_prompt,
    gate_passed,
    mean_score,
    parse_json_content,
    threshold_for_mode,
)


def test_threshold_for_mode() -> None:
    assert threshold_for_mode("freeform") == 0.4
    assert threshold_for_mode("spec") == 0.2


def test_gate_passed() -> None:
    assert gate_passed(0.25, "freeform") is True
    assert gate_passed(0.5, "freeform") is False
    assert gate_passed(0.19, "spec") is True


def test_mean_score() -> None:
    assert mean_score(
        {
            "goals": 0.0,
            "acceptance": 0.25,
            "boundaries": 0.25,
            "alternatives": 0.5,
            "assumptions": 0.25,
        }
    ) == pytest.approx(0.25)


def test_parse_json_content_strips_fence() -> None:
    payload = parse_json_content(
        """```json
        {"question": "Which runtime?", "recommended_answer": "Dedicated Sandbox"}
        ```"""
    )
    assert payload["recommended_answer"] == "Dedicated Sandbox"


def test_build_implementation_prompt_numbered_conditions() -> None:
    prompt = build_implementation_prompt(TETRIS_FALLBACK_SPEC)
    assert "1. Dedicated Sandbox" in prompt
    assert "非目標:" in prompt
    assert "受け入れ基準:" in prompt


def test_grill_loop_exits_after_score_failures_without_spinning() -> None:
    from ai_tool.grill_me_loop import run_grill_me_loop

    calls = {"n": 0}

    def flaky_chat(**kwargs):
        calls["n"] += 1
        user = str((kwargs.get("messages") or [])[-1]["content"])
        if "Ask the next highest-value unresolved question" in user:
            return type(
                "Resp",
                (),
                {
                    "message": type(
                        "Msg",
                        (),
                        {
                            "content": (
                                '{"question":"Where?","recommended_answer":"Sandbox",'
                                '"dimension":"boundaries","rationale":"isolate"}'
                            )
                        },
                    )()
                },
            )()
        raise ValueError("invalid score json")

    result = run_grill_me_loop(
        "テトリスを作って",
        model="mock",
        max_rounds=8,
        min_rounds_before_score=1,
        max_score_failures=2,
        chat_fn=flaky_chat,
    )
    assert result.fallback_used
    assert calls["n"] <= 4


def test_grill_loop_exits_when_gate_passes_without_ready_flag() -> None:
    from ai_tool.grill_me_loop import run_grill_me_loop

    def chat(**kwargs):
        user = str((kwargs.get("messages") or [])[-1]["content"])
        if "Ask the next highest-value unresolved question" in user:
            payload = {
                "question": "Where?",
                "recommended_answer": "Sandbox",
                "dimension": "boundaries",
                "rationale": "isolate",
            }
        else:
            payload = {
                "dimensions": {
                    "goals": 0.25,
                    "acceptance": 0.25,
                    "boundaries": 0.0,
                    "alternatives": 0.25,
                    "assumptions": 0.25,
                },
                "aggregate": 0.2,
                "weakest": [],
                "ready_to_exit": False,
                "aligned_spec": {"title": "Tetris", "summary": "sandbox"},
            }
        import json

        return type(
            "Resp",
            (),
            {"message": type("Msg", (), {"content": json.dumps(payload)})()},
        )()

    result = run_grill_me_loop(
        "テトリスを作って",
        model="mock",
        max_rounds=5,
        min_rounds_before_score=1,
        chat_fn=chat,
    )
    assert result.gate_passed
    assert not result.fallback_used
    assert result.rounds == 1
