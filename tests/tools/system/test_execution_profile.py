from __future__ import annotations

import pytest

from tools.system.execution_profile import (
    ExecutionProfileNotFoundError,
    agent_turn_phase_profile,
    apply_execution_profile,
    messages_have_images,
    resolve_execution_profile,
)


def test_resolve_structured_output_think_false() -> None:
    resolved = resolve_execution_profile("structured_output")
    assert resolved["think"] is False
    assert resolved["execution_profile_id"] == "structured_output"


def test_resolve_human_intent_think_true() -> None:
    resolved = resolve_execution_profile("human_intent")
    assert resolved["think"] is True


def test_vision_reasoning_switches_on_images() -> None:
    without = resolve_execution_profile("vision_reasoning", has_images=False)
    with_images = resolve_execution_profile("vision_reasoning", has_images=True)
    assert without["think"] is False
    assert with_images["think"] is True


def test_apply_execution_profile_respects_explicit_think_override() -> None:
    merged = apply_execution_profile({"messages": []}, "structured_output", has_images=False)
    assert merged["think"] is False
    merged_override = apply_execution_profile(
        {"messages": [], "think": True},
        "structured_output",
    )
    assert merged_override["think"] is True


def test_agent_turn_phase_mapping() -> None:
    assert agent_turn_phase_profile("agent_initial_llm") == "human_intent"
    assert agent_turn_phase_profile("agent_post_tool_llm") == "fast_tool"
    assert agent_turn_phase_profile("local_review_llm") == "deep_reasoning"


def test_messages_have_images() -> None:
    assert messages_have_images([{"role": "user", "content": "hi", "images": ["abc"]}])
    assert not messages_have_images([{"role": "user", "content": "hi"}])


def test_unknown_profile_raises() -> None:
    with pytest.raises(ExecutionProfileNotFoundError):
        resolve_execution_profile("missing_profile")
