from ... import config


class ScoreRenderer:
    """Draw each side's authoritative snapshot score in its HUD panel."""

    _MARGIN_X = 16
    _LABEL_Y = 40
    _SCORE_Y = 80

    def __init__(self, geometry):
        """Store the board geometry used to place each panel's text."""
        self._geometry = geometry

    def render(self, canvas, snapshot) -> None:
        """Draw White's score in the left panel and Black's score in the right panel."""
        # side_panel.png's top section is a circular badge (outer half)
        # + a text plaque (board-facing half). SCORE_LEFT_TEXT_X lands
        # inside the plaque on the left panel; the right panel is mirrored
        # by BackgroundLoader so its plaque is already board-facing, right
        # where _MARGIN_X puts it.
        left_x = config.SCORE_LEFT_TEXT_X
        right_x = self._geometry.board_origin_x + self._geometry.window_width + self._MARGIN_X

        self._draw_side(canvas, left_x, "White", snapshot.scores["w"])
        self._draw_side(canvas, right_x, "Black", snapshot.scores["b"])

    def _draw_side(self, canvas, x, label, score) -> None:
        """Draw one side's label and score, stacked vertically at x."""
        canvas.put_text(label, x, self._LABEL_Y, config.SCORE_FONT_SIZE, config.SCORE_TEXT_COLOR)
        canvas.put_text(str(score), x, self._SCORE_Y, config.SCORE_FONT_SIZE, config.SCORE_TEXT_COLOR)
