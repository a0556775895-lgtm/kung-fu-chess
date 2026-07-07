from PieceFactory import PieceFactory

class Board:
    CELL_SIZE = 100

    def __init__(self, board_lines):
        self._grid = []
        self._rows = 0
        self._cols = 0

        self._selected_position = None

        self._current_time = 0

        self._pending_source = None
        self._pending_destination = None
        self._pending_finish_time = None

        self._parse_board(board_lines)

    def _parse_board(self, board_lines):
        first_row_width = None

        for row in board_lines:
            tokens = row.split()

            if first_row_width is None:
                first_row_width = len(tokens)
            elif len(tokens) != first_row_width:
                raise ValueError("ROW_WIDTH_MISMATCH")

            current_row = []

            for token in tokens:
                if token == ".":
                    current_row.append(None)
                else:
                    current_row.append(PieceFactory.create_piece(token))

            self._grid.append(current_row)

        self._rows = len(self._grid)
        self._cols = first_row_width

    def click(self, x, y):
        row, col = self._pixel_to_cell(x, y)

        if not self._is_inside_board(row, col):
            return

        if self._selected_position is None:
            self._handle_click_without_selection(row, col)
        else:
            self._handle_click_with_selection(row, col)

    def wait(self, milliseconds):
        self._current_time += milliseconds

        if (
            self._pending_finish_time is not None
            and self._current_time >= self._pending_finish_time
        ):
            self._execute_pending_move()

    def print_board(self):
        for row in self._grid:
            print(" ".join(str(piece) if piece else "." for piece in row))

    def _pixel_to_cell(self, x, y):
        return y // self.CELL_SIZE, x // self.CELL_SIZE

    def _is_inside_board(self, row, col):
        return (
            0 <= row < self._rows and
            0 <= col < self._cols
        )

    def _handle_click_without_selection(self, row, col):
        if self._grid[row][col] is not None:
            self._selected_position = (row, col)

    def _handle_click_with_selection(self, row, col):
        clicked = self._grid[row][col]

        selected_row, selected_col = self._selected_position
        selected_piece = self._grid[selected_row][selected_col]

        # Clicking another friendly piece replaces the selection.
        if (
            clicked is not None
            and clicked.color == selected_piece.color
        ):
            self._selected_position = (row, col)
            return

        # Ignore illegal moves.
        if not selected_piece.is_valid_move(
            selected_row,
            selected_col,
            row,
            col,
        ):
            self._selected_position = None
            return

        self._pending_source = self._selected_position
        self._pending_destination = (row, col)

        self._pending_finish_time = (
            self._current_time + selected_piece.get_move_time()
        )

        self._selected_position = None

    def _execute_pending_move(self):
        source_row, source_col = self._pending_source
        dest_row, dest_col = self._pending_destination

        piece = self._grid[source_row][source_col]

        self._grid[source_row][source_col] = None
        self._grid[dest_row][dest_col] = piece

        self._pending_source = None
        self._pending_destination = None
        self._pending_finish_time = None