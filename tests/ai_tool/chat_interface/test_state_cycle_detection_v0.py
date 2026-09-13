"""State-cycle Detection v0 tests."""
from __future__ import annotations

import json
from pathlib import Path

from ai_tool.chat_interface.progress_classification_v0 import (
    ProgressStateSnapshot,
    classify_progress_transition,
)
from ai_tool.chat_interface.state_cycle_detection_v0 import (
    StateCycleTracker,
    normalize_action_class,
    state_fingerprint_from_snapshot,
    transition_fingerprint,
)

REPO = Path(__file__).resolve().parents[3]


def _stable_state() -> ProgressStateSnapshot:
    return ProgressStateSnapshot(
        gap_kind="",
        gap_resolved=False,
        answer_gate_verified=True,
        unsatisfied_conditions=["answer produced"],
        satisfied_conditions=["relevant evidence observed"],
        verified_evidence_ids=["E1"],
        goal_statuses={"G1": "in_progress", "G1.1": "in_progress"},
        task_statuses={"T1": "complete", "T2": "in_progress"},
        completion_ratio=0.5,
        requirements_passed=1,
        requirements_total=2,
        passed_condition_ids=["relevant evidence observed"],
        failed_condition_ids=[],
        failure_signature=None,
    )


def test_unchanged_state_and_repeated_transition_shadow_b_pattern():
    tracker = StateCycleTracker()
    stable = _stable_state()
    prior = None
    first_unchanged = None
    first_repeated = None
    first_candidate = None
    for seq in range(1, 8):
        current = stable
        classification = classify_progress_transition(prior, current)
        args = (
            {"path": "PROJECT_SPEC.md", "offset": 1, "limit": 50}
            if seq >= 4
            else {"limit": 50, "path": "PROJECT_SPEC.md"}
        )
        row = tracker.observe_step(
            tool_sequence=seq,
            prior_snapshot=prior,
            current_snapshot=current,
            classification=classification,
            tool_name="read_file",
            tool_arguments=args,
            tool_status="success",
            evidence_gain=seq == 1,
            relevance_audit="ACCEPT",
            mutation_count=0,
        )
        if row["unchanged_state"] and first_unchanged is None:
            first_unchanged = seq
        if row["repeated_transition"] and first_repeated is None:
            first_repeated = seq
        if row["state_cycle_candidate"] and first_candidate is None:
            first_candidate = seq
        prior = current

    assert first_unchanged == 2
    assert first_repeated == 3
    assert first_candidate == 3
    assert tracker.first_repeated_transition_tool_sequence == 3
    assert tracker.first_cycle_candidate_tool_sequence == 3


def test_action_changed_without_state_progress_on_argument_variation():
    tracker = StateCycleTracker()
    stable = _stable_state()
    prior = stable
    classification = classify_progress_transition(prior, stable)
    tracker.observe_step(
        tool_sequence=1,
        prior_snapshot=None,
        current_snapshot=stable,
        classification=classification,
        tool_name="read_file",
        tool_arguments={"limit": 50, "path": "PROJECT_SPEC.md"},
        tool_status="success",
        evidence_gain=False,
        relevance_audit="ACCEPT",
        mutation_count=0,
    )
    row = tracker.observe_step(
        tool_sequence=2,
        prior_snapshot=stable,
        current_snapshot=stable,
        classification=classify_progress_transition(stable, stable),
        tool_name="read_file",
        tool_arguments={"path": "PROJECT_SPEC.md", "offset": 1, "limit": 50},
        tool_status="success",
        evidence_gain=False,
        relevance_audit="ACCEPT",
        mutation_count=0,
    )
    assert row["unchanged_state"] is True
    assert row["action_changed_without_state_progress"] is True
    assert row["repeated_transition"] is False


def test_case_001_pagination_is_exploration_not_cycle():
    tracker = StateCycleTracker()
    prior = ProgressStateSnapshot(
        satisfied_conditions=[],
        unsatisfied_conditions=["relevant evidence observed"],
        verified_evidence_ids=[],
        task_statuses={"T1": "in_progress"},
    )
    first = tracker.observe_step(
        tool_sequence=1,
        prior_snapshot=None,
        current_snapshot=prior,
        classification=classify_progress_transition(None, prior),
        tool_name="search_files",
        tool_arguments={"query": "clear_full_lines", "path": "."},
        tool_status="partial",
        evidence_gain=False,
        relevance_audit="ACCEPT",
        mutation_count=0,
    )
    assert first["state_cycle_candidate"] is False

    growing = ProgressStateSnapshot(
        satisfied_conditions=[],
        unsatisfied_conditions=["relevant evidence observed"],
        verified_evidence_ids=["E1", "E2"],
        task_statuses={"T1": "in_progress"},
    )
    row = tracker.observe_step(
        tool_sequence=2,
        prior_snapshot=prior,
        current_snapshot=growing,
        classification=classify_progress_transition(prior, growing),
        tool_name="search_files",
        tool_arguments={
            "query": "clear_full_lines",
            "path": ".",
            "after": "ai_tool/catalog/entries/local_read_url_text.json",
        },
        tool_status="partial",
        evidence_gain=True,
        relevance_audit="ACCEPT",
        mutation_count=0,
    )
    assert row["unchanged_state"] is False
    assert row["action_changed_without_state_progress"] is False
    assert row["repeated_transition"] is False
    assert row["state_cycle_candidate"] is False
    assert normalize_action_class(
        "search_files",
        {"query": "clear_full_lines", "path": ".", "after": "x"},
    ) == normalize_action_class(
        "search_files",
        {"query": "clear_full_lines", "path": ".", "after": "y"},
    )


def test_state_fingerprint_excludes_action():
    snap = _stable_state()
    fp = state_fingerprint_from_snapshot(snap)
    assert "read_file" not in json.dumps(fp.as_dict())


def test_shadow_b_session_replay_via_simulated_snapshots():
    """Replay Shadow B tool 1-7 using stable-state simulation (READ-ONLY proxy)."""
    tracker = StateCycleTracker()
    prior = None
    stable = _stable_state()
    markers = []
    for seq in range(1, 8):
        current = stable
        classification = classify_progress_transition(prior, current)
        row = tracker.observe_step(
            tool_sequence=seq,
            prior_snapshot=prior,
            current_snapshot=current,
            classification=classification,
            tool_name="read_file",
            tool_arguments={"path": "PROJECT_SPEC.md", "offset": 1, "limit": 50},
            tool_status="success",
            evidence_gain=seq == 1,
            relevance_audit="ACCEPT",
            mutation_count=0,
        )
        markers.append(
            (
                seq,
                row["unchanged_state"],
                row["repeated_transition"],
                row["state_cycle_candidate"],
            )
        )
        prior = current

    assert markers[1][1] is True  # tool 2 unchanged
    assert markers[2][2] is True  # tool 3 repeated_transition
    assert markers[2][3] is True  # tool 3 cycle_candidate
    assert tracker.first_repeated_transition_tool_sequence == 3
    assert tracker.first_cycle_candidate_tool_sequence == 3
    assert tracker.first_cycle_candidate_tool_sequence < 6
