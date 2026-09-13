"""Collision: out of 10x20 grid or overlap with occupied cells.

Gap: 衝突判定の実装
Spec: 移動後座標が範囲外、または既存ブロックと重なるとき衝突。
Does not move, lock, draw, or clear lines.
"""
from __future__ import annotations

from typing import Any, Iterator

GRID_WIDTH = 10
GRID_HEIGHT = 20


def empty_grid() -> list[list[int]]:
    return [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]


def occupied_cells(piece: dict[str, Any]) -> Iterator[tuple[int, int]]:
    shape = piece.get("shape") or []
    ox = int(piece.get("x") or 0)
    oy = int(piece.get("y") or 0)
    for row_i, row in enumerate(shape):
        for col_i, cell in enumerate(row):
            if cell:
                yield ox + col_i, oy + row_i


def collides(piece: dict[str, Any], grid: list[list[int]]) -> bool:
    for x, y in occupied_cells(piece):
        if x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT:
            return True
        if grid[y][x]:
            return True
    return False
