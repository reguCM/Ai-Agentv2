"""Try-move, try-rotate against collision, and 500ms fall-due check.

Gap: テトロミノの落下・移動・回転
Spec: move/rotate the piece; fall every ~500ms via caller-supplied ticks.
Does not lock, spawn next, handle keys, draw, or game over.
"""
from __future__ import annotations

from typing import Any

from research.grill_observation_v0.medium_task_reality_v0.workspace.collision import collides
from research.grill_observation_v0.medium_task_reality_v0.workspace.tetromino import rotate

FALL_INTERVAL_MS = 500


def try_move(piece: dict[str, Any], grid: list[list[int]], dx: int, dy: int) -> bool:
    candidate = {
        "kind": piece.get("kind"),
        "shape": piece.get("shape"),
        "x": int(piece.get("x") or 0) + int(dx),
        "y": int(piece.get("y") or 0) + int(dy),
    }
    if collides(candidate, grid):
        return False
    piece["x"] = candidate["x"]
    piece["y"] = candidate["y"]
    return True


def try_rotate(piece: dict[str, Any], grid: list[list[int]]) -> bool:
    candidate = {
        "kind": piece.get("kind"),
        "shape": rotate(piece.get("shape") or []),
        "x": piece.get("x"),
        "y": piece.get("y"),
    }
    if collides(candidate, grid):
        return False
    piece["shape"] = candidate["shape"]
    return True


def fall_due(now_ms: int, last_fall_ms: int, interval_ms: int = FALL_INTERVAL_MS) -> bool:
    return (int(now_ms) - int(last_fall_ms)) >= int(interval_ms)
