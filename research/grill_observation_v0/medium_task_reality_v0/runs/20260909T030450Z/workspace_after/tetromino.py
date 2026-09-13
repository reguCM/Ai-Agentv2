"""Tetromino shapes, rotation, and top-of-grid spawn.

Gap: テトロミノの形状と初期配置の実装
Spec: 2D arrays; rotate by transpose and reverse; initial y is top of grid.
Does not move, collide, draw, or clear lines.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SHAPES: dict[str, list[list[int]]] = {
    "I": [[1, 1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "Z": [[1, 1, 0], [0, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
}

KINDS = tuple(SHAPES.keys())


def rotate(shape: list[list[int]]) -> list[list[int]]:
    """Rotate by reverse then transpose, as specified."""
    if not shape:
        return []
    reversed_rows = shape[::-1]
    return [list(row) for row in zip(*reversed_rows)]


def spawn(kind: str) -> dict[str, Any]:
    if kind not in SHAPES:
        raise KeyError(kind)
    return {
        "kind": kind,
        "shape": deepcopy(SHAPES[kind]),
        "x": 0,
        "y": 0,
    }
