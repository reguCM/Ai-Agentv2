"""Experimental LibA demo client (fixture for technology A). Not Production."""
from __future__ import annotations

import pytest

from ai_tool.experimental.liba_demo_tool.client import parse_a_payload


def test_parse_object():
    assert parse_a_payload('{"x": 1}') == {"x": 1}


def test_reject_array():
    with pytest.raises(TypeError):
        parse_a_payload("[1]")


def test_reject_invalid_json():
    with pytest.raises(Exception):
        parse_a_payload("nope")
