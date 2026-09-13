"""Tetromino shape and spawn tests. No pygame, no infinite loop."""
from __future__ import annotations

from research.grill_observation_v0.medium_task_reality_v0.workspace import tetromino as t


def test_all_seven_kinds_are_2d_arrays() -> None:
    assert set(t.KINDS) == {"I", "O", "T", "S", "Z", "J", "L"}
    for kind in t.KINDS:
        shape = t.SHAPES[kind]
        assert shape
        assert all(isinstance(row, list) for row in shape)


def test_rotate_uses_transpose_and_reverse() -> None:
    original = [[1, 1, 1, 1]]
    rotated = t.rotate(original)
    assert rotated == [[1], [1], [1], [1]]
    assert original == [[1, 1, 1, 1]]


def test_spawn_at_top_of_grid() -> None:
    piece = t.spawn("T")
    assert piece["y"] == 0
    assert piece["x"] == 0
    assert piece["kind"] == "T"
    assert piece["shape"] == t.SHAPES["T"]
    piece["shape"][0][0] = 9
    assert t.SHAPES["T"][0][0] == 0
