"""Tests for choosing winner-specific game-over artwork."""

from types import SimpleNamespace

import numpy as np

from engine.snapshot import GameSnapshot
from view.game_over.game_over_renderer import GameOverRenderer
from view.img import Img


def _snapshot(*, game_over: bool, winner_color: str | None) -> GameSnapshot:
    return GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[],
        selected_cell=None,
        game_over=game_over,
        winner_color=winner_color,
    )


def test_game_over_renderer_leaves_active_game_unchanged():
    geometry = SimpleNamespace(canvas_width=24, canvas_height=16)
    renderer = GameOverRenderer(geometry)
    renderer.load()
    canvas = Img()
    canvas.img = np.zeros((16, 24, 4), dtype=np.uint8)
    before = canvas.img.copy()

    renderer.render(canvas, _snapshot(game_over=False, winner_color=None))

    assert np.array_equal(canvas.img, before)


def test_game_over_renderer_selects_different_artwork_for_each_winner():
    geometry = SimpleNamespace(canvas_width=24, canvas_height=16)
    renderer = GameOverRenderer(geometry)
    renderer.load()
    white_canvas = Img()
    white_canvas.img = np.zeros((16, 24, 4), dtype=np.uint8)
    black_canvas = Img()
    black_canvas.img = np.zeros((16, 24, 4), dtype=np.uint8)

    renderer.render(white_canvas, _snapshot(game_over=True, winner_color="w"))
    renderer.render(black_canvas, _snapshot(game_over=True, winner_color="b"))

    assert np.any(white_canvas.img)
    assert np.any(black_canvas.img)
    assert not np.array_equal(white_canvas.img, black_canvas.img)
