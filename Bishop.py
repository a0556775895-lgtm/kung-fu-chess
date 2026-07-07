from Piece import Piece


class Bishop(Piece):
    """Represents a bishop chess piece."""

    def __init__(self, color):
        super().__init__(color, "B", 2000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return row_distance == col_distance and row_distance > 0