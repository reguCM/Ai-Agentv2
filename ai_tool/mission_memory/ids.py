"""IDs for Mission / Execution / Evidence. Path-segment safe. Not order."""
from __future__ import annotations

import uuid


def new_mission_id() -> str:
    return "m" + uuid.uuid4().hex


def new_execution_id() -> str:
    return "x" + uuid.uuid4().hex


def new_persistent_evidence_id() -> str:
    return "pe" + uuid.uuid4().hex
