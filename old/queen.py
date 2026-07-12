from old.piece import Piece


class Queen(Piece):
    """Represents a queen chess piece.

    Queen moves like rook + bishop; `is_valid_move` enforces that.
    """

    def __init__(self, color):
        super().__init__(color, "Q", 1000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece,):
        """Return True if the move is a valid queen move (straight or diagonal)."""

        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return (
            (row_distance == col_distance and row_distance > 0) or
            (row_distance == 0 and col_distance > 0) or
            (col_distance == 0 and row_distance > 0)
        )

    def get_path_cells(self, source_row, source_col, destination_row, destination_col):
        """Return intermediate cells between source and destination.

        Supports both straight-line (rook-like) and diagonal (bishop-like)
        movement. Caller expects a list of (row, col) tuples excluding source
        and destination.
        """
        path = []

        row_step = (destination_row > source_row) - (destination_row < source_row)
        col_step = (destination_col > source_col) - (destination_col < source_col)

        # If both steps are zero then no path.
        if row_step == 0 and col_step == 0:
            return path

        row, col = source_row + row_step, source_col + col_step
        while (row, col) != (destination_row, destination_col):
            path.append((row, col))
            row += row_step
            col += col_step

        return path