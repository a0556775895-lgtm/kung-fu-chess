from Piece import Piece


class Queen(Piece):
    """Represents a queen chess piece."""

    def __init__(self, color):
        super().__init__(color, "Q", 2000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece,):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return (
            (row_distance == col_distance and row_distance > 0) or
            (row_distance == 0 and col_distance > 0) or
            (col_distance == 0 and row_distance > 0)
        )