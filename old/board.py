from old.piece_factory import PieceFactory
from old.piece import PieceColor
from old.board_geometry import BoardGeometry
from old.pending_move import PendingMove
from old.selection_controller import SelectionController

class Board:
    CELL_SIZE = 100

    def __init__(self, board_lines):
        """Create a Board from text lines.

        `board_lines` is a list of strings where each token is space-separated.
        """
        self._grid = []
        self._rows = 0
        self._cols = 0
        self._current_time = 0
        self._game_over = False

        self._pending_move = PendingMove()
        self._geometry = BoardGeometry(0, 0, self.CELL_SIZE)
        self._selection_controller = SelectionController(self)

        self._parse_board(board_lines)
        self._geometry.update_dimensions(self._rows, self._cols)

    @property
    def _pending_source(self):
        return self._pending_move.source

    @_pending_source.setter
    def _pending_source(self, value):
        self._pending_move.source = value

    @property
    def _pending_destination(self):
        return self._pending_move.destination

    @_pending_destination.setter
    def _pending_destination(self, value):
        self._pending_move.destination = value

    @property
    def _pending_arrival_time(self):
        return self._pending_move.arrival_time

    @_pending_arrival_time.setter
    def _pending_arrival_time(self, value):
        self._pending_move.arrival_time = value

    @property
    def _pending_finish_time(self):
        return self._pending_move.finish_time

    @_pending_finish_time.setter
    def _pending_finish_time(self, value):
        self._pending_move.finish_time = value

    @property
    def _selected_position(self):
        return self._selection_controller.selected_position

    @_selected_position.setter
    def _selected_position(self, value):
        self._selection_controller.selected_position = value

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

        if self._pending_move.finish_time is not None:
            return

        row, col = self._pixel_to_cell(x, y)

        if not self._is_inside_board(row, col):
            return

        self._selection_controller.handle_click(row, col)

    def wait(self, milliseconds):
        self._current_time += milliseconds

        if self._pending_move.is_arrival_pending(self._current_time):
            self._execute_arrival()

        if self._pending_move.is_finish_pending(self._current_time):
            self._finish_pending_move()

        for row in self._grid:
            for piece in row:
                if piece is not None and piece.should_finish_jump(self._current_time):
                    piece.finish_jump()

    def print_board(self):
        for row in self._grid:
            print(" ".join(str(piece) if piece else "." for piece in row))

    def _pixel_to_cell(self, x, y):
        return self._geometry.pixel_to_cell(x, y)

    def _is_inside_board(self, row, col):
        return self._geometry.is_inside_board(row, col)

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
            self._pending_move.mark_executed()
            return

        self._grid[source_row][source_col] = None
        self._grid[dest_row][dest_col] = piece

        if (
            piece.symbol == "P"
            and (
                (piece.color == PieceColor.WHITE and dest_row == 0)
                or
                (piece.color == PieceColor.BLACK and dest_row == self._rows - 1)
            )
        ):
            self._grid[dest_row][dest_col] = PieceFactory.create_piece(
                f"{piece.color.value}Q"
            )

        if (
            captured_piece is not None
            and captured_piece.is_royal()
        ):
            self._game_over = True

        self._pending_move.mark_executed()

    def _finish_pending_move(self):
        self._pending_move.clear()

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

    def get_piece_at(self, row, col):
        """Return the piece at (row, col), or None if empty."""
        return self._grid[row][col]

    def is_path_clear(self, piece, source_row, source_col, destination_row, destination_col):
        """Return True if no piece blocks the path for this move."""
        return self._is_path_clear(piece, source_row, source_col, destination_row, destination_col)

    @property
    def current_time(self):
        return self._current_time

    def schedule_move(self, source, destination, arrival_time, finish_time):
        """Register a pending move to be executed over time."""
        self._pending_move.set_move(source, destination, arrival_time, finish_time)
    

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