"""Tests that score rendering consumes authoritative snapshot data only."""

from types import SimpleNamespace

from engine.snapshot import GameSnapshot
from view.hud.score.score_renderer import ScoreRenderer


class _RecordingCanvas:
    def __init__(self):
        self.texts = []

    def put_text(self, text, x, y, font_size, color):
        self.texts.append((text, x, y, font_size, color))


def test_score_renderer_reads_scores_from_snapshot():
    geometry = SimpleNamespace(board_origin_x=221, window_width=480)
    renderer = ScoreRenderer(geometry)
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[],
        selected_cell=None,
        game_over=False,
        scores={"w": 7, "b": 4},
        player_names={"w": "Alice", "b": "Bob"},
    )
    canvas = _RecordingCanvas()

    renderer.render(canvas, snapshot)

    rendered_text = [entry[0] for entry in canvas.texts]
    assert rendered_text == ["Alice", "7", "Bob", "4"]
