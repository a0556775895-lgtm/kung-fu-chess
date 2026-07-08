class SelectionController:
    """Track board selection and translate clicks into pending moves."""

    def __init__(self, board):
        self._board = board
        self._selected_position = None

    @property
    def selected_position(self):
        return self._selected_position

    @selected_position.setter
    def selected_position(self, value):
        self._selected_position = value

    def handle_click(self, row, col):
        if self._selected_position is None:
            self._try_select_piece(row, col)
        else:
            self._handle_selected_click(row, col)

    def _try_select_piece(self, row, col):
        if self._board.get_piece_at(row, col) is not None:
            self._selected_position = (row, col)

    def _handle_selected_click(self, row, col):
        clicked_piece = self._board.get_piece_at(row, col)
        source_row, source_col = self._selected_position
        selected_piece = self._board.get_piece_at(source_row, source_col)

        if (
            clicked_piece is not None
            and clicked_piece.color == selected_piece.color
        ):
            self._selected_position = (row, col)
            return

        if not selected_piece.is_valid_move(
            source_row,
            source_col,
            row,
            col,
            clicked_piece,
        ):
            self._selected_position = None
            return

        if not self._board.is_path_clear(
            selected_piece,
            source_row,
            source_col,
            row,
            col,
        ):
            self._selected_position = None
            return

        path = selected_piece.get_path_cells(
            source_row,
            source_col,
            row,
            col,
        )

        steps = len(path) + 1
        move_time = selected_piece.move_time * steps
        arrival_time = self._board.current_time + selected_piece.move_time
        finish_time = self._board.current_time + move_time

        self._board.schedule_move(
            self._selected_position,
            (row, col),
            arrival_time,
            finish_time,
        )

        self._selected_position = None
