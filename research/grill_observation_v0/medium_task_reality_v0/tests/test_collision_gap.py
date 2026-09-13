"""Collision tests. No pygame, no movement implementation."""
from __future__ import annotations

from research.grill_observation_v0.medium_task_reality_v0.workspace import collision as c
from research.grill_observation_v0.medium_task_reality_v0.workspace.tetromino import spawn


def test_empty_grid_top_t_does_not_collide() -> None:
    piece = spawn("T")
    assert c.collides(piece, c.empty_grid()) is False


def test_out_of_grid_is_collision() -> None:
    piece = spawn("I")
    piece["x"] = 8
    assert c.collides(piece, c.empty_grid()) is True


def test_overlap_occupied_is_collision() -> None:
    piece = spawn("O")
    grid = c.empty_grid()
    grid[0][0] = 1
    assert c.collides(piece, grid) is True
