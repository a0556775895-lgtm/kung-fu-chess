# ניהול בחירה ותרגום קליקים לפקודות GameEngine.
"""Tracks the selected cell and translates clicks into GameEngine commands.

Does not decide chess legality and does not call RuleEngine directly.
On a second click: if the target is a friendly piece, the selection
switches to it; otherwise request_move is called and selection clears.
"""

from model.position import Position


class Controller:
    """Track the current selection and turn clicks into GameEngine
    commands."""

    def __init__(self, board, game_engine, board_mapper):
        self._board = board
        self._game_engine = game_engine
        self._board_mapper = board_mapper
        self._selected_position = None

    @property
    def selected_position(self):
        return self._selected_position

    def handle_pixel_click(self, x, y):
        """Entry point from the view/main loop. Converts pixels to a
        cell and applies the in/out-of-board selection rules (section
        11) before delegating to `handle_click`."""
        position = self._board_mapper.pixel_to_position(x, y)

        if not self._board_mapper.is_inside_board(position):
            if self._selected_position is not None:
                # A piece is selected: an outside-board click cancels
                # the selection and sends no command to GameEngine.
                self._selected_position = None
            # No selection: outside-board clicks are ignored.
            return

        self.handle_click(position)

    def handle_click(self, position: Position):
        if self._selected_position is None:
            self._try_select_piece(position)
        else:
            self._handle_selected_click(position)

    def _try_select_piece(self, position: Position):
        # Ignore first clicks on empty cells (section 11).
        if self._board.get_piece_at(position) is not None:
            self._selected_position = position

    def _handle_selected_click(self, position: Position):
        source = self._selected_position
        clicked_piece = self._board.get_piece_at(position)
        selected_piece = self._board.get_piece_at(source)

        if (
            clicked_piece is not None
            and selected_piece is not None
            and clicked_piece.color == selected_piece.color
        ):
            self._selected_position = position
            return

        self._game_engine.request_move(source, position)
        self._selected_position = None