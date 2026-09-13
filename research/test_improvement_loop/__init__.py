"""テスト改善ループ (test_improvement_loop).

Compatibility alias remains at research.auto_upgrade_system.
"""
from research.test_improvement_loop.orchestrator import Orchestrator, StageViolation
from research.test_improvement_loop.schema import (
    DISPLAY_NAME,
    INTERNAL_ID,
    MAX_UPGRADE_ATTEMPTS,
)

__all__ = [
    "DISPLAY_NAME",
    "INTERNAL_ID",
    "MAX_UPGRADE_ATTEMPTS",
    "Orchestrator",
    "StageViolation",
]
