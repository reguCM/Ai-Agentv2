"""Clear full rows, shift remaining rows down, add to score.

Gap: 行の削除（ラインクリア）のロジック
Spec: 埋まっている行を削除し、上を下へシフトし、スコアを加算。
Does not lock pieces, move, draw, or define a point table.
"""
from __future__ import annotations


def clear_full_lines(grid: list[list[int]]) -> tuple[list[list[int]], int]:
    if not grid:
        return [], 0
    width = len(grid[0])
    kept = [list(row) for row in grid if not all(cell for cell in row)]
    cleared = len(grid) - len(kept)
    while len(kept) < len(grid):
        kept.insert(0, [0] * width)
    return kept, cleared


def add_score(score: int, lines_cleared: int) -> int:
    return int(score) + int(lines_cleared)
