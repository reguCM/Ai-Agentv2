"""Game over when a newly spawned piece collides at the top.

Gap: ゲームオーバーの判定条件
Spec: cannot place a new tetromino at the initial top position.
Does not lock, restart, draw, or handle input.
"""
from __future__ import annotations

from research.grill_observation_v0.medium_task_reality_v0.workspace.collision import collides
from research.grill_observation_v0.medium_task_reality_v0.workspace.tetromino import spawn


def is_game_over(kind: str, grid: list[list[int]]) -> bool:
    return collides(spawn(kind), grid)
