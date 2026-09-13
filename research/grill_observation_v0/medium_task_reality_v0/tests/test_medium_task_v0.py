import pytest
from workspace.window_loop import update, grid, score

def test_line_clear_adds_score():
    # Setup
    grid = [[1 for _ in range(10)] for _ in range(20)]  # All filled
    score = 0
    # Call update
    update()
    # Check that grid is cleared and score is updated
    assert grid == [[0 for _ in range(10)] for _ in range(20)]
    assert score == 20  # Assuming 20 lines cleared, each adding 1 point
