"""Tests for post-baseline architecture exploration."""
from __future__ import annotations

from ai_tool.web_tool_post_baseline_architecture_exploration import (
    architecture_options,
    select_option,
)


def test_select_stop_a_when_baseline_pass():
    opts = architecture_options(True, {"confirmed": []})
    sel, _why, stop, rejected = select_option(True, opts, {})
    assert sel == "OPT0_NO_ACTION"
    assert stop == "STOP_A"
    assert len(rejected) >= 3


def test_architecture_has_minimum_options():
    opts = architecture_options(True, {})
    assert len(opts) >= 4
    ids = {o["id"] for o in opts}
    assert "OPT0_NO_ACTION" in ids
