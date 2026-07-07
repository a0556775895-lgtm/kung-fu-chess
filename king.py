from piece import Piece


class King(Piece):
    """Represents a king chess piece."""

    def __init__(self, color):
        super().__init__(color, "K", 1000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece,):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return max(row_distance, col_distance) == 1