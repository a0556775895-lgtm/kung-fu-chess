from piece import Piece


class Pawn(Piece):
    """Represents a pawn chess piece."""

    def __init__(self, color):
        super().__init__(color, "P", 1000)

    def is_valid_move(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
    ):
        return False