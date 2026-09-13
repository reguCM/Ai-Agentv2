"""Unit tests for shared revalidation protocol helpers."""
from __future__ import annotations

from ai_tool.revalidation_protocol import (
    ChangeLineagePair,
    build_propagation_run_report,
    canonical_change_lineage_set,
    change_lineage_set_identity,
    normalize_change_lineage_pair,
    normalize_semantic_revalidation_outcome,
)


def test_normalize_semantic_revalidation_outcome_defaults_unknown_to_cannot_determine():
    assert normalize_semantic_revalidation_outcome("needs_revision") == "needs_revision"
    assert normalize_semantic_revalidation_outcome("bogus") == "cannot_determine"


def test_change_lineage_pair_identity_is_order_independent():
    rows = [
        normalize_change_lineage_pair("b", "b2"),
        ("a", "a2"),
    ]
    assert canonical_change_lineage_set(rows) == (("a", "a2"), ("b", "b2"))
    assert change_lineage_set_identity(rows) == "a->a2|b->b2"


def test_change_lineage_pair_accepts_legacy_upstream_keys():
    pair = ChangeLineagePair.from_mapping(
        {"old_upstream_task_id": "old", "new_upstream_task_id": "new"}
    )
    assert pair is not None
    assert pair.as_dict() == {"old_task_id": "old", "new_task_id": "new"}


def test_build_propagation_run_report_sets_converged_from_stop_reason():
    payload = build_propagation_run_report(
        propagation_id="pw-test",
        completed_wave_count=2,
        processed_change_sets=["a->b"],
        successor_history=[],
        held_tasks=[],
        stop_reason="converged",
        waves=[],
        converged_stop_reason="converged",
    )
    assert payload["converged"] is True
    assert payload["completed_wave_index"] == 1
