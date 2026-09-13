"""Line-clear tests. No pygame, no piece locking."""
from __future__ import annotations

from research.grill_observation_v0.completion_gap_v0.workspace.collision import empty_grid
from research.grill_observation_v0.completion_gap_v0.workspace.line_clear import add_score, clear_full_lines


def test_full_row_removed_and_shifted() -> None:
    grid = empty_grid()
    grid[19] = [1] * 10
    grid[18][0] = 1
    new_grid, cleared = clear_full_lines(grid)
    assert cleared == 1
    assert new_grid[19][0] == 1
    assert all(cell == 0 for cell in new_grid[18])
    assert len(new_grid) == 20


def test_no_full_row() -> None:
    grid = empty_grid()
    grid[19][0] = 1
    new_grid, cleared = clear_full_lines(grid)
    assert cleared == 0
    assert new_grid[19][0] == 1


def test_score_increments_by_cleared_count() -> None:
    assert add_score(0, 2) == 2
