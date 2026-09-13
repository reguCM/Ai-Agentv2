from __future__ import annotations

import pytest

from research.test_improvement_loop.orchestrator import Orchestrator, StageViolation


def test_canary_rejects_five_ids():
    orch = Orchestrator()
    with pytest.raises(StageViolation):
        orch.assert_can_run(["a", "b", "c", "d", "e"])


def test_canary_allows_exactly_one():
    orch = Orchestrator()
    orch.assert_can_run(["only"])


def test_cannot_skip_to_validate_5():
    orch = Orchestrator()
    assert orch.stage == "CANARY_1"
    with pytest.raises(StageViolation):
        orch.assert_can_run(["1", "2", "3", "4", "5"])


def test_advance_then_validate_5():
    orch = Orchestrator()
    assert orch.confirm_and_advance(ok=True, reasons=[], next_stage="VALIDATE_5")
    orch.assert_can_run(["a", "b", "c", "d", "e"])
    with pytest.raises(StageViolation):
        orch.assert_can_run(["only"])


def test_confirm_fail_stops():
    orch = Orchestrator()
    assert not orch.confirm_and_advance(ok=False, reasons=["false AUTO"], next_stage="VALIDATE_5")
    assert orch.stage == "STOP"
    with pytest.raises(StageViolation):
        orch.assert_can_run(["x"])


def test_attempt_cap():
    orch = Orchestrator(max_attempts=2)
    orch.begin_attempt()
    orch.begin_attempt()
    with pytest.raises(StageViolation):
        orch.begin_attempt()
    assert orch.stage == "STOP"
