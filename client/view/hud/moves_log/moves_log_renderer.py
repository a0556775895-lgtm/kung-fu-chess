# ציור טבלת המהלכים (Time/Move) בכל פאנל HUD צדי.
from ... import config


class MovesLogRenderer:
    """Draws each side's move log as a Time/Move table, stacked below the
    existing score block in the same HUD panel. Pulls entries from
    MovesLogData (memory only) -- never computes notation or timing itself."""

    _MARGIN_X = 16

    def __init__(self, moves_log_data, geometry):
        """Store the move log data source and board geometry used to place each panel's table."""
        self._moves_log_data = moves_log_data
        self._geometry = geometry

    def render(self, canvas, snapshot) -> None:
        """Draw White's move log in the left panel and Black's in the right panel."""
        left_x = self._MARGIN_X
        right_x = self._geometry.board_origin_x + self._geometry.window_width + self._MARGIN_X

        self._draw_panel(canvas, left_x, self._moves_log_data.white_entries)
        self._draw_panel(canvas, right_x, self._moves_log_data.black_entries)

    def _draw_panel(self, canvas, x, entries) -> None:
        """Draw the "Time"/"Move" header at x, then as many trailing
        entries (newest last) as fit the panel's remaining height."""
        header_y = config.MOVES_LOG_HEADER_Y
        canvas.put_text("Time", x + config.MOVES_LOG_TIME_COL_X, header_y,
                         config.MOVES_LOG_FONT_SIZE, config.SCORE_TEXT_COLOR)
        canvas.put_text("Move", x + config.MOVES_LOG_MOVE_COL_X, header_y,
                         config.MOVES_LOG_FONT_SIZE, config.SCORE_TEXT_COLOR)

        visible_rows = self._visible_row_count()
        for row_index, entry in enumerate(entries[-visible_rows:] if visible_rows else []):
            row_y = header_y + (row_index + 1) * config.MOVES_LOG_ROW_HEIGHT
            canvas.put_text(entry.time_str, x + config.MOVES_LOG_TIME_COL_X, row_y,
                             config.MOVES_LOG_FONT_SIZE, config.SCORE_TEXT_COLOR)
            canvas.put_text(entry.notation, x + config.MOVES_LOG_MOVE_COL_X, row_y,
                             config.MOVES_LOG_FONT_SIZE, config.SCORE_TEXT_COLOR)

    def _visible_row_count(self) -> int:
        """How many move rows fit between the header and the bottom of
        side_panel.png's parchment area, without spilling onto the plaque
        below it."""
        available_height = (
            config.MOVES_LOG_BOTTOM_Y - config.MOVES_LOG_HEADER_Y - config.MOVES_LOG_ROW_HEIGHT
        )
        return max(0, available_height // config.MOVES_LOG_ROW_HEIGHT)
