from old.piece import Piece


class Knight(Piece):
    """Represents a knight chess piece.
    Knight moves in L-shapes (2x1 or 1x2); `is_valid_move` enforces that.
    """

    def __init__(self, color, move_time=3000, jump_duration=3000):
         super().__init__(color, "N", move_time, jump_duration)


    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece):
        """Return True if the knight move is a legal L-shaped jump."""
        # destination_piece is required by the Piece interface (all subclasses must
        # share the same signature for polymorphism), but Knight doesn't need it:
        # a knight can jump to any square in its L-shape pattern, occupied or not.
     
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return (
            (row_distance == 2 and col_distance == 1) or
            (row_distance == 1 and col_distance == 2)
        )