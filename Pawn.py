from Piece import Piece


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
        destination_piece,
    ):
        if destination_piece is None:
            return self._is_valid_forward_move(
                source_row,
                source_col,
                destination_row,
                destination_col,
            )

        return self._is_valid_capture(
            source_row,
            source_col,
            destination_row,
            destination_col,
            destination_piece,
        )

    def _is_valid_forward_move(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
    ):
        direction = -1 if self.color == "w" else 1

        return (
            destination_row == source_row + direction
            and destination_col == source_col
        )

    def _is_valid_capture(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
        destination_piece,
    ):
        direction = -1 if self.color == "w" else 1

        return (
            destination_piece.color != self.color
            and destination_row == source_row + direction
            and abs(destination_col - source_col) == 1
        )