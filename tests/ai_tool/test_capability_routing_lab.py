"""Capability Routing Lab unit tests (mocked chat_fn)."""
from __future__ import annotations

from unittest import mock

from ai_tool.capability_routing_lab import (
    build_workers,
    default_tool_task,
    run_arm_a_direct,
    run_arm_b_routed,
    summarize_routing_lab,
)


def test_build_workers_marks_deepseek_ineligible_for_tool_calling():
    workers = build_workers(
        ["deepseek_coder_v2_16b", "qwen3_14b"],
        required_capabilities=["tool_calling"],
        probe_fn=lambda model: (
            {"supported": False, "error": "does not support tools"}
            if "deepseek" in model
            else {"supported": True, "error": None}
        ),
    )
    deepseek = next(row for row in workers if row.worker_id == "deepseek_coder_v2_16b")
    qwen = next(row for row in workers if row.worker_id == "qwen3_14b")
    assert deepseek.eligible is False
    assert qwen.eligible is True
    assert "tool_calling" not in deepseek.effective_capabilities


def test_arm_b_skips_ineligible_and_routes_to_eligible_worker():
    task = default_tool_task()
    workers = build_workers(
        ["deepseek_coder_v2_16b", "qwen3_14b"],
        required_capabilities=task.required_capabilities,
        probe_fn=lambda model: (
            {"supported": False, "error": "does not support tools"}
            if "deepseek" in model
            else {"supported": True, "error": None}
        ),
    )

    def _chat(**kwargs):
        fn = mock.Mock()
        fn.name = "echo_probe"
        fn.arguments = {"text": "ROUTING_LAB_OK"}
        msg = mock.Mock()
        msg.content = ""
        msg.tool_calls = [mock.Mock(function=fn)]
        return mock.Mock(message=msg)

    arm_a = run_arm_a_direct(
        workers,
        task,
        primary_worker_id="deepseek_coder_v2_16b",
        chat_fn=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("does not support tools")),
    )
    arm_b = run_arm_b_routed(workers, task, chat_fn=_chat)
    summary = summarize_routing_lab(arm_a + arm_b)
    assert summary["arm_a_success"] is False
    assert summary["arm_b_success"] is True
    assert summary["routing_demonstrated"] is True
    assert summary["arm_b_selected_worker"] == "qwen3_14b"
