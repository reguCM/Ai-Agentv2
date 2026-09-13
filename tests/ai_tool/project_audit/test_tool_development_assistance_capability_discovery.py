"""Tests for TDA Capability Discovery Phase C."""
from __future__ import annotations

from ai_tool.experimental.development_assistance.capability_discovery import (
    evaluate_catalog_decisions,
    observe_from_run,
    phase_c_cases,
    run_capability_discovery,
    select_c3_candidate,
)
from ai_tool.experimental.development_assistance.harness import run_tda_case
from ai_tool.experimental.development_assistance.fixtures import tda_evaluation_cases


def test_phase_c_has_six_cases():
    assert len(phase_c_cases()) == 6


def test_observe_gate_reuse_case1():
    tdc_id, _, spec = phase_c_cases()[0]
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    obs = observe_from_run(tdc_id, spec, r)
    assert any(o.decision == "REUSE" and o.stage == "Research Gate" for o in obs)


def test_observe_urscript_api_existence():
    tdc_id, _, spec = next(c for c in phase_c_cases() if c[0] == "TDC-4")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    obs = observe_from_run(tdc_id, spec, r)
    assert any("CAP-C" in o.id or "Function Existence" in o.idea for o in obs)


def test_sandbox_runner_deferred():
    tdc_id, _, spec = next(c for c in phase_c_cases() if c[0] == "TDC-2")
    r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
    obs = observe_from_run(tdc_id, spec, r)
    assert any(o.decision == "DEFER" and "Sandbox" in o.idea for o in obs)


def test_catalog_has_ten_candidates():
    obs = []
    for tdc_id, _, spec in phase_c_cases():
        r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
        obs.extend(observe_from_run(tdc_id, spec, r))
    cat = evaluate_catalog_decisions(obs)
    assert len(cat) == 10


def test_c3_not_implemented_by_default():
    obs = []
    for tdc_id, _, spec in phase_c_cases():
        r = run_tda_case(spec, mode="llm_web", llm_enabled=False)
        obs.extend(observe_from_run(tdc_id, spec, r))
    cat = evaluate_catalog_decisions(obs)
    c3 = select_c3_candidate(cat)
    assert c3 is not None
    assert c3.get("implement_this_phase") is False


def test_capability_discovery_offline():
    result = run_capability_discovery(llm_enabled=False, fetch_live_baseline=False)
    assert result["production_changes"] == []
    assert result["c3_implemented"] is False
    assert result["observation_count"] >= 15
    assert result["decision"] in ("CONTINUE", "INVESTIGATE", "EXPERIMENTAL_RETAIN", "STOP_NO_NEW_CORE")
    assert result["lifecycle_summary"]["reuse"] >= 5
