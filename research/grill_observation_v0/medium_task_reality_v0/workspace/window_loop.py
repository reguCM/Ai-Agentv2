"""Pygame window init and one-step game loop skeleton.

This module covers only the first Completion Gap:
window 300x600 + QUIT loop + empty update/draw + flip.
It does not implement tetromino, grid, collision, or scoring.
"""
from __future__ import annotations

import pygame

SCREEN_WIDTH = 300
SCREEN_HEIGHT = 600


def init_window() -> pygame.Surface:
    pygame.init()
    return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


def handle_events() -> bool:
    """Return False when a QUIT event is seen."""
    running = True
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    return running


def update() -> None:
    global grid, score
    from workspace.line_clear import clear_full_lines, add_score
    grid, lines_cleared = clear_full_lines(grid)
    score = add_score(score, lines_cleared)


def draw(screen: pygame.Surface) -> None:
    pygame.display.flip()


def run_one_iteration(screen: pygame.Surface) -> bool:
    running = handle_events()
    if running:
        update()
        draw(screen)
    return running


def shutdown() -> None:
    pygame.quit()


def run_forever() -> None:
    screen = init_window()
    running = True
    while running:
        running = run_one_iteration(screen)
    shutdown()


if __name__ == "__main__":
    run_forever()
