"""Tests for Web Tool Evaluation Canonical Migration."""
from __future__ import annotations

from ai_tool.agent_integration.eval_production_parity_bridge import loop_to_trial_executions
from ai_tool.web_tool_evaluation_canonical_migration import (
    harness_inventory,
    run_web_tool_evaluation_canonical_migration,
)
from ai_tool.web_tool_practical_evaluation import EVAL_CASES, run_deterministic_practical_case


def test_harness_inventory_m1_m3_migrated():
    inv = harness_inventory()
    by_id = {h["id"]: h for h in inv}
    assert by_id["M1"]["status"] == "migrated"
    assert by_id["M2"]["status"] == "migrated"
    assert by_id["M3"]["status"] == "migrated"


def test_deterministic_case_not_production_equivalent():
    det = run_deterministic_practical_case(EVAL_CASES[0])
    assert det["production_equivalent"] is False
    assert det["diagnostic_only"] is True
    assert det["scored"] is False


def test_loop_to_trial_executions_adapter():
    from ai_tool.agent_integration.eval_production_parity_bridge import run_canonical_web_eval
    from ai_tool.agent_integration.trial import make_mock_chat_fn
    from ai_tool.agent_integration.trial_scenarios import TrialScenario

    scenario = TrialScenario(
        "adapt", "q", "search_web", "",
        mock_tool_calls=[{"name": "search_web", "arguments": {"query": "q"}}],
        mock_final_answer="ok",
    )
    loop, _meta = run_canonical_web_eval(
        "q",
        chat_fn=make_mock_chat_fn(scenario),
        model="mock",
        search_web_fn=lambda **_k: {"ok": True, "hits": [], "backends_tried": ["fixture"]},
        max_rounds=2,
    )
    records = loop_to_trial_executions(loop)
    assert records
    assert records[0].selection.tool_name == "search_web"


def test_migration_run(fetch_live_baseline=False):
    result = run_web_tool_evaluation_canonical_migration(fetch_live_baseline=False)
    assert result["production_changes"] == []
    assert result["path_divergence"]["gap_confirmed"] is True
    assert result["stop_integrity"]["diagnostic"]["allowed"] is False
    assert result["stop_integrity"]["canonical"]["allowed"] is True
    assert result["cc01_assessment"]["final_classification"] == "RETAIN_CORE"
