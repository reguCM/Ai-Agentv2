"""Tests for core capability discovery challenge."""
from __future__ import annotations

from ai_tool.core_capability_discovery_challenge import (
    assess_mechanical_verification,
    discover_future_capabilities,
    run_core_capability_discovery_challenge,
    specification_change_requests,
)


def test_discovers_max_three_candidates():
    caps = discover_future_capabilities()
    assert 1 <= len(caps) <= 3
    ids = {c.id for c in caps}
    assert len(ids) == len(caps)


def test_candidates_have_classification():
    for c in discover_future_capabilities():
        assert c.classification in ("C0", "C1", "C2", "C3", "C4", "C5")
        assert c.matrix.evidence


def test_mechanical_verification_retain():
    mech = assess_mechanical_verification()
    assert mech["retain_without_production"] is True
    assert mech["production_connection"] == "NOT RECOMMENDED at current measured failure rates"
    assert mech["mechanical_answer_separation"] == "CLEAR — verify_answer does not replace LLM output"


def test_specification_change_request_present():
    scrs = specification_change_requests()
    assert len(scrs) >= 1
    assert scrs[0].human_decision_required is True


def test_run_challenge():
    result = run_core_capability_discovery_challenge(fetch_live_baseline=False)
    assert result["overall"] in ("PASS", "PARTIAL")
    assert len(result["discovered_capabilities"]) <= 3
    assert "RECORD_FUTURE_CAPABILITIES" in result["decisions"]
    assert result["production_changes"] == []
    assert result["specification_change_requests"] != "NONE"
