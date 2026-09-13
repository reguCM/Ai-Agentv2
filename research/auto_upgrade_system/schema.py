"""Compatibility alias. Canonical: research.test_improvement_loop.schema."""
from research.test_improvement_loop.schema import *  # noqa: F401,F403
from research.test_improvement_loop.schema import (  # noqa: F401
    DISPLAY_NAME,
    INTERNAL_ID,
    LEGACY_INTERNAL_ID,
    LEGACY_PACKAGE,
    MAX_UPGRADE_ATTEMPTS,
    STAGE_MAX_N,
    STAGES,
    empty_run,
    new_candidate,
    new_case,
)
