"""Tests for autonomous improvement harness."""
from __future__ import annotations

from ai_tool.web_tool_autonomous_improvement import generate_options, select_option


def test_select_stop_d_when_golden_and_e2e_pass():
    assessment = {"live_e2e_pass": True, "golden_pass": True, "eval_gap_confirmed": True}
    opts = generate_options(assessment)
    sel, _why, stop = select_option(opts, assessment)
    assert sel == "OPT_STOP_D"
    assert stop == "STOP_D"


def test_select_stop_a_when_golden_fail():
    assessment = {"live_e2e_pass": False, "golden_pass": False}
    opts = generate_options(assessment)
    sel, _why, stop = select_option(opts, assessment)
    assert stop == "STOP_A"
