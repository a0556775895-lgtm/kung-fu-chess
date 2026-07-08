from piece import Piece


class Pawn(Piece):
    """Represents a pawn chess piece.

    Movement and capture logic lives in `is_valid_move`. `get_path_cells`
    returns intermediate cells for two-square initial moves.
    """

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
        """Return True if the pawn move from source to destination is legal.

        Handles forward moves and captures based on `destination_piece`.
        """

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
        board = self.get_board()
        rows = board.get_rows()

        if self.color == "w":
            start_row = rows - 1
        else:
            start_row = 0
        # One-cell move.
        if (
            destination_row == source_row + direction
            and destination_col == source_col
        ):
            return True

        # Two-cell move from the starting row.
        return (
            source_row == start_row
            and destination_row == source_row + (2 * direction)
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
    
    def get_path_cells(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
    ):
        """Return intermediate cells for a two-square pawn move.

        Returns a list with the cell the pawn passes through when moving
        two squares forward from its starting row; otherwise empty list.
        """
        if abs(destination_row - source_row) == 2:
            direction = -1 if self.color == "w" else 1

            return [
                (source_row + direction, source_col)
            ]

        return []