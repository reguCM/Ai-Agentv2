"""S9 — tool_argument_validation against canonical $defs/test_plan."""
from __future__ import annotations

import pytest

from test_safety.tool_argument_validation import (
    extract_optional_authorization_packet,
    extract_test_plan_from_arguments,
    validate_test_plan_object,
)

MINIMAL_PLAN = {
    "plan_id": "s9-val",
    "commands": ["echo ok"],
    "declared_primary_risk_level": "LEVEL_1",
    "declared_dimensions": {"llm": "NONE", "gpu": "NONE", "network": "NONE"},
}


def test_extract_test_plan_valid():
    plan = extract_test_plan_from_arguments({"test_plan": MINIMAL_PLAN})
    assert plan["plan_id"] == "s9-val"


def test_extract_test_plan_missing():
    with pytest.raises(ValueError, match="test_plan"):
        extract_test_plan_from_arguments({})


def test_validate_rejects_empty_commands():
    bad = {**MINIMAL_PLAN, "commands": []}
    with pytest.raises(Exception):
        validate_test_plan_object(bad)


def test_optional_authorization_absent():
    assert extract_optional_authorization_packet({}) is None


def test_optional_authorization_present():
    pkt = {"authorization_id": "x"}
    assert extract_optional_authorization_packet({"authorization_packet": pkt}) == pkt
