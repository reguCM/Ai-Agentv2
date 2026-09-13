"""Gap 1 tests: window init and one-iteration loop. No GUI, no infinite while."""
from __future__ import annotations

import pygame

from research.grill_observation_v0.completion_gap_v0.workspace import window_loop as wl


def test_init_creates_300x600_surface() -> None:
    screen = wl.init_window()
    try:
        assert screen.get_width() == 300
        assert screen.get_height() == 600
    finally:
        wl.shutdown()


def test_one_iteration_then_quit() -> None:
    screen = wl.init_window()
    try:
        running = wl.run_one_iteration(screen)
        assert running is True
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        running = wl.run_one_iteration(screen)
        assert running is False
    finally:
        wl.shutdown()


def test_shutdown_reaches_pygame_quit() -> None:
    wl.init_window()
    wl.shutdown()
    assert pygame.get_init() is False
