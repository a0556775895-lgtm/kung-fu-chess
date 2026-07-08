from PieceFactory import PieceFactory

class Board:
    CELL_SIZE = 100

    def __init__(self, board_lines):
        self._grid = []
        self._rows = 0
        self._cols = 0

        self._pending_arrival_time = None
        self._pending_move_executed = False

        self._selected_position = None

        self._current_time = 0

        self._pending_source = None
        self._pending_destination = None
        self._pending_finish_time = None

        self._parse_board(board_lines)

        self._game_over = False

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
                    piece = PieceFactory.create_piece(token)
                    piece.set_board(self)
                    current_row.append(piece)

            self._grid.append(current_row)

        self._rows = len(self._grid)
        self._cols = first_row_width

    def click(self, x, y):
        if self._game_over:
            return
        
        if self._pending_finish_time is not None:
            return
        row, col = self._pixel_to_cell(x, y)

        if not self._is_inside_board(row, col):
            return

        if self._selected_position is None:
            self._handle_click_without_selection(row, col)
        else:
            self._handle_click_with_selection(row, col)

    def wait(self, milliseconds):
        self._current_time += milliseconds

        # Arrival
        if (
            self._pending_arrival_time is not None
            and not self._pending_move_executed
            and self._current_time >= self._pending_arrival_time
        ):
            self._execute_arrival()

        # Finish
        if (
            self._pending_finish_time is not None
            and self._current_time >= self._pending_finish_time
        ):
            self._finish_pending_move()

        for row in self._grid:
            for piece in row:
                if (
                    piece is not None
                    and piece.should_finish_jump(self._current_time)
                ):
                    piece.finish_jump()

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
            clicked,
        ):
            self._selected_position = None
            return

        # Ignore moves blocked by another piece.
        if not self._is_path_clear(
            selected_piece,
            selected_row,
            selected_col,
            row,
            col,
        ):
            self._selected_position = None
            return

        self._pending_source = self._selected_position
        self._pending_destination = (row, col)

        path = selected_piece.get_path_cells(
            selected_row,
            selected_col,
            row,
            col,
        )

        steps = len(path) + 1

        move_time = selected_piece.get_move_time() * steps

        self._pending_arrival_time = (
            self._current_time +
            selected_piece.get_move_time()
        )

        self._pending_move_executed = False
        self._pending_finish_time = (
            self._current_time + move_time
        )

        self._selected_position = None

    def _execute_arrival(self):
        source_row, source_col = self._pending_source
        dest_row, dest_col = self._pending_destination

        piece = self._grid[source_row][source_col]
        captured_piece = self._grid[dest_row][dest_col]

        if (
            captured_piece is not None
            and captured_piece.color != piece.color
            and captured_piece.is_airborne()
        ):
            self._grid[source_row][source_col] = None
            self._pending_move_executed = True
            return

        self._grid[source_row][source_col] = None
        self._grid[dest_row][dest_col] = piece

        if (
            piece.symbol == "P"
            and (
                (piece.color == "w" and dest_row == 0)
                or
                (piece.color == "b" and dest_row == self._rows - 1)
            )
        ):
            self._grid[dest_row][dest_col] = PieceFactory.create_piece(
                f"{piece.color}Q"
            )

        if (
            captured_piece is not None
            and captured_piece.symbol == "K"
        ):
            self._game_over = True

        self._pending_move_executed = True

    def _finish_pending_move(self):
        self._pending_source = None
        self._pending_destination = None

        self._pending_arrival_time = None
        self._pending_finish_time = None

        self._pending_move_executed = False

    def _is_path_clear(
        self,
        piece,
        source_row,
        source_col,
        destination_row,
        destination_col,
        ):
            path = piece.get_path_cells(
                source_row,
                source_col,
                destination_row,
                destination_col,
            )

            for row, col in path:
                if self._grid[row][col] is not None:
                    return False

            return True
    
    def get_rows(self):
        return self._rows
    

    def jump(self, x, y):
        if self._game_over:
            return

        row, col = self._pixel_to_cell(x, y)

        if not self._is_inside_board(row, col):
            return

        piece = self._grid[row][col]

        if piece is None:
            return

        if self._pending_source == (row, col):
            return

        if piece.is_airborne():
            return

        piece.start_jump(self._current_time)