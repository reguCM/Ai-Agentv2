"""Tests for CC-01 Eval Production Parity Bridge."""
from __future__ import annotations

import pytest

from ai_tool.agent_integration.eval_production_parity_bridge import (
    PATH_CANONICAL,
    PATH_DIAGNOSTIC_DIRECT,
    EvalPathMetadata,
    assert_diagnostic_not_scored,
    compare_path_divergence,
    defensive_core_policy,
    infer_search_backend,
    path_metadata_from_direct,
    run_canonical_web_eval,
    run_diagnostic_direct_eval,
    validate_stop_decision_integrity,
)
from ai_tool.agent_integration.gpu_process_e2e import execute_registry_tool
from ai_tool.agent_integration.trial import make_mock_chat_fn
from ai_tool.agent_integration.trial_scenarios import TrialScenario
from ai_tool.eval_production_parity_bridge_evaluation import (
    run_eval_production_parity_bridge_evaluation,
    run_path_separation_verification,
    run_stop_decision_integrity,
)


def test_infer_search_backend_trial_mock():
    backend, mol = infer_search_backend(
        {"hits": [{"backend": "trial_mock", "url": "https://example.com"}], "backends_tried": ["trial_mock"]}
    )
    assert backend == "trial_mock"
    assert mol == "mock"


def test_canonical_path_production_equivalent():
    scenario = TrialScenario(
        scenario_id="canonical_meta",
        user_request="q",
        expected_tool="search_web",
        routing_note="meta test",
        mock_tool_calls=[{"name": "search_web", "arguments": {"query": "q"}}],
        mock_final_answer="answer",
    )

    def _fixture_search(**_kw):
        return {"ok": True, "hits": [], "backends_tried": ["fixture"]}

    _loop, meta = run_canonical_web_eval(
        "q",
        chat_fn=make_mock_chat_fn(scenario),
        model="mock",
        search_web_fn=_fixture_search,
        max_rounds=2,
    )
    assert meta.production_equivalent is True
    assert meta.diagnostic_only is False
    assert meta.web_session_tracker is True
    assert meta.path_label == PATH_CANONICAL
    assert meta.can_drive_production_decision() is True


def test_diagnostic_path_not_production_equivalent():
    _rec, meta = run_diagnostic_direct_eval("search_web", {"query": "nonsense_xyz"})
    assert meta.production_equivalent is False
    assert meta.diagnostic_only is True
    assert meta.boundary_applied is False
    assert meta.web_session_tracker is False
    assert meta.path_label == PATH_DIAGNOSTIC_DIRECT
    assert meta.can_drive_production_decision() is False
    assert meta.backend == "trial_mock"


def test_mock_direct_cannot_drive_stop_no_change():
    _rec, meta = run_diagnostic_direct_eval("search_web", {"query": "nonsense"})
    check = validate_stop_decision_integrity(decision="STOP_NO_CHANGE", path_meta=meta)
    assert check["allowed"] is False
    assert "SCR-01" in check["reason"] or "diagnostic" in check["reason"].lower()


def test_path_divergence_gap():
    div = compare_path_divergence()
    assert div["gap_confirmed"] is True
    assert div["diagnostic"]["hit_count"] == 3
    assert div["canonical"]["hit_count"] == 0
    assert div["mock_pass_implies_production_pass"] is False


def test_assert_diagnostic_not_scored_raises():
    meta = EvalPathMetadata(
        path_label=PATH_DIAGNOSTIC_DIRECT,
        backend="trial_mock",
        production_equivalent=False,
        mock_or_live="mock",
        boundary_applied=False,
        web_session_tracker=False,
        diagnostic_only=True,
        scored=True,
    )
    with pytest.raises(ValueError, match="SCR-01"):
        assert_diagnostic_not_scored(meta)


def test_path_metadata_from_direct_execute_registry_tool():
    rec = execute_registry_tool("search_web", {"query": "zzzz"})
    meta = path_metadata_from_direct(rec, tool_name="search_web")
    assert meta.production_equivalent is False
    assert len(rec.result.get("hits") or []) == 3


def test_defensive_core_policy_structure():
    policy = defensive_core_policy()
    assert "policy_version" in policy
    assert "classification" in policy
    assert "C3" in policy["classification"]


def test_path_separation_verification():
    result = run_path_separation_verification()
    assert result["pass"] is True


def test_stop_decision_integrity_harness():
    result = run_stop_decision_integrity()
    assert result["pass"] is True


def test_run_evaluation_harness():
    result = run_eval_production_parity_bridge_evaluation(fetch_live_baseline=False)
    assert result["cc01_implemented"] is True
    assert result["production_changes"] == []
    assert result["path_separation"]["pass"] is True
    assert result["stop_decision_integrity"]["pass"] is True
    assert result["canonical_smoke"]["pass"] is True
    # Live URL cases skipped when fetch_live=False; full golden runs in runner
    assert result["golden_baseline"]["pass_count"] >= 2
