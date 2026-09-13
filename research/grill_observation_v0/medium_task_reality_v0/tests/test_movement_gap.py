"""Move / rotate-in-place / fall-interval tests. No pygame, no lock."""
from __future__ import annotations

from research.grill_observation_v0.medium_task_reality_v0.workspace.collision import empty_grid
from research.grill_observation_v0.medium_task_reality_v0.workspace.movement import (
    fall_due,
    try_move,
    try_rotate,
)
from research.grill_observation_v0.medium_task_reality_v0.workspace.tetromino import SHAPES, spawn


def test_move_accepted_until_wall() -> None:
    piece = spawn("I")
    grid = empty_grid()
    assert try_move(piece, grid, 6, 0) is True
    assert piece["x"] == 6
    assert try_move(piece, grid, 1, 0) is False
    assert piece["x"] == 6


def test_rotate_rejected_when_would_overlap() -> None:
    piece = spawn("I")
    grid = empty_grid()
    grid[1][0] = 1
    assert try_rotate(piece, grid) is False
    assert piece["shape"] == SHAPES["I"]


def test_fall_due_at_500ms() -> None:
    assert fall_due(499, 0) is False
    assert fall_due(500, 0) is True
