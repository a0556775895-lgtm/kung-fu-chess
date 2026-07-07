from piece import Piece


class Knight(Piece):
    """Represents a knight chess piece."""

    def __init__(self, color):
        super().__init__(color, "N", 3000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece,):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return (
            (row_distance == 2 and col_distance == 1) or
            (row_distance == 1 and col_distance == 2)
        )