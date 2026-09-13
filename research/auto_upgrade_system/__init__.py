"""Compatibility alias for テスト改善ループ.

Canonical package: research.test_improvement_loop
Legacy id: auto_upgrade_system

New code should import research.test_improvement_loop.
This package re-exports the canonical modules so existing import paths
do not break.
"""
from research.test_improvement_loop import (
    DISPLAY_NAME,
    INTERNAL_ID,
    MAX_UPGRADE_ATTEMPTS,
    Orchestrator,
    StageViolation,
)

__all__ = [
    "DISPLAY_NAME",
    "INTERNAL_ID",
    "MAX_UPGRADE_ATTEMPTS",
    "Orchestrator",
    "StageViolation",
]
