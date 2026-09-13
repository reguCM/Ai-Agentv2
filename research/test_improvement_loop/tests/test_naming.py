from __future__ import annotations

from pathlib import Path

from research.test_improvement_loop.schema import (
    DISPLAY_NAME,
    INTERNAL_ID,
    LEGACY_PACKAGE,
)


def test_display_name_and_internal_id():
    assert DISPLAY_NAME == "テスト改善ループ"
    assert INTERNAL_ID == "test_improvement_loop"
    assert LEGACY_PACKAGE == "research.auto_upgrade_system"


def test_legacy_package_alias_is_same_orchestrator():
    from research.auto_upgrade_system.orchestrator import Orchestrator as Legacy
    from research.test_improvement_loop.orchestrator import Orchestrator as Canonical

    assert Legacy is Canonical


def test_past_runs_and_human_review_remain():
    package = Path(__file__).resolve().parents[1]
    root = package.parents[1]
    holdout = package / "runs" / "20260908T223431Z" / "stage_holdout_5.json"
    q36_review = package / "runs" / "20260908T224940Z" / "HUMAN_REVIEW.md"
    q36_before = package / "runs" / "20260908T224940Z" / "before.json"
    v0_review = package / "runs" / "20260908T223431Z" / "HUMAN_REVIEW.md"
    legacy_holdout = (
        root
        / "research"
        / "auto_upgrade_system"
        / "runs"
        / "20260908T223431Z"
        / "stage_holdout_5.json"
    )
    assert holdout.is_file()
    assert q36_before.is_file()
    assert "Before" in q36_review.read_text(encoding="utf-8")
    assert "After" in q36_review.read_text(encoding="utf-8")
    assert "Before" in v0_review.read_text(encoding="utf-8")
    assert "After" in v0_review.read_text(encoding="utf-8")
    assert legacy_holdout.is_file()
