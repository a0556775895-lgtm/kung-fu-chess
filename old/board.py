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
        self.rows = 0
        self.cols = 0
        self._current_time = 0
        self._game_over = False

        self._pending_move = PendingMove()
        self._geometry = BoardGeometry(0, 0, self.CELL_SIZE)
        self._selection_controller = SelectionController(self)

        self._parse_board(board_lines)
        self._geometry.update_dimensions(self.rows, self.cols)

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
        firstrow_width = None

        for row in board_lines:
            tokens = row.split()

            if firstrow_width is None:
                firstrow_width = len(tokens)
            elif len(tokens) != firstrow_width:
                raise ValueError("ROW_WIDTH_MISMATCH")

            currentrow = []

            for token in tokens:
                if token == ".":
                    currentrow.append(None)
                else:
                    piece = PieceFactory.create_piece(token)
                    piece.set_board(self)
                    currentrow.append(piece)

            self._grid.append(currentrow)

        self.rows = len(self._grid)
        self.cols = firstrow_width

    def click(self, x, y):
        if self._game_over:
            return

        if self._pending_move.finish_time is not None:
            return

        row, col = self._pixel_tocell(x, y)

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

    def _pixel_tocell(self, x, y):
        return self._geometry.pixel_tocell(x, y)

    def _is_inside_board(self, row, col):
        return self._geometry.is_inside_board(row, col)

    def _execute_arrival(self):
        sourcerow, sourcecol = self._pending_source
        destrow, destcol = self._pending_destination

        piece = self._grid[sourcerow][sourcecol]
        captured_piece = self._grid[destrow][destcol]

        if (
            captured_piece is not None
            and captured_piece.color != piece.color
            and captured_piece.is_airborne()
        ):
            self._grid[sourcerow][sourcecol] = None
            self._pending_move.mark_executed()
            return

        self._grid[sourcerow][sourcecol] = None
        self._grid[destrow][destcol] = piece

        if (
            piece.symbol == "P"
            and (
                (piece.color == PieceColor.WHITE and destrow == 0)
                or
                (piece.color == PieceColor.BLACK and destrow == self.rows - 1)
            )
        ):
            self._grid[destrow][destcol] = PieceFactory.create_piece(
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
        sourcerow,
        sourcecol,
        destinationrow,
        destinationcol,
        ):
            path = piece.get_pathcells(
                sourcerow,
                sourcecol,
                destinationrow,
                destinationcol,
            )

            for row, col in path:
                if self._grid[row][col] is not None:
                    return False

            return True
    
    

    def get_piece_at(self, row, col):
        """Return the piece at (row, col), or None if empty."""
        return self._grid[row][col]

    def is_path_clear(self, piece, sourcerow, sourcecol, destinationrow, destinationcol):
        """Return True if no piece blocks the path for this move."""
        return self._is_path_clear(piece, sourcerow, sourcecol, destinationrow, destinationcol)

    @property
    def current_time(self):
        return self._current_time

    def schedule_move(self, source, destination, arrival_time, finish_time):
        """Register a pending move to be executed over time."""
        self._pending_move.set_move(source, destination, arrival_time, finish_time)
    

    def jump(self, x, y):
        if self._game_over:
            return

        row, col = self._pixel_tocell(x, y)

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