from piece import Piece


class King(Piece):
    """Represents a king chess piece.

    King can move one square in any direction; logic implemented in
    `is_valid_move`.
    """

    def __init__(self, color, move_time=1000, jump_duration=1000):
         super().__init__(color, "K", move_time, jump_duration)


    def is_valid_move(self, source_row, source_col, destination_row, destination_col, destination_piece):
        """Return True if the king move is a single-step move in any direction."""
        # destination_piece not used: king can move to any square within range,
        # occupied or not (Board handles same-color/capture logic separately).

        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return max(row_distance, col_distance) == 1
    
    def is_royal(self):
        """Return True - capturing this piece ends the game."""
        return True