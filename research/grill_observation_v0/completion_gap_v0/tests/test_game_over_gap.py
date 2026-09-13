"""Game-over tests. No pygame, no lock, no restart."""
from __future__ import annotations

from research.grill_observation_v0.completion_gap_v0.workspace.collision import empty_grid
from research.grill_observation_v0.completion_gap_v0.workspace.game_over import is_game_over


def test_empty_grid_is_not_game_over() -> None:
    assert is_game_over("T", empty_grid()) is False


def test_blocked_top_is_game_over() -> None:
    grid = empty_grid()
    grid[0] = [1] * 10
    assert is_game_over("T", grid) is True


def test_occupied_below_spawn_is_not_game_over() -> None:
    grid = empty_grid()
    grid[5] = [1] * 10
    assert is_game_over("O", grid) is False
