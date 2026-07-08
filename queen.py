from piece import Piece


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