from old.piece import Piece, PieceColor


class Pawn(Piece):
    """Represents a pawn chess piece.

    Movement and capture logic lives in `is_valid_move`. `get_pathcells`
    returns intermediate cells for two-square initial moves.
    """

    def __init__(self, color):
        super().__init__(color, "P", 1000)

    def is_valid_move(
        self,
        sourcerow,
        sourcecol,
        destinationrow,
        destinationcol,
        destination_piece,
    ):
        """Return True if the pawn move from source to destination is legal.

        Handles forward moves and captures based on `destination_piece`.
        """

        if destination_piece is None:
            return self._is_valid_forward_move(
                sourcerow,
                sourcecol,
                destinationrow,
                destinationcol,
            )

        return self._is_valid_capture(
            sourcerow,
            sourcecol,
            destinationrow,
            destinationcol,
            destination_piece,
        )

    def _is_valid_forward_move(
        self,
        sourcerow,
        sourcecol,
        destinationrow,
        destinationcol,
    ):
        direction = -1 if self.color == PieceColor.WHITE else 1
        board = self.get_board()
        rows = board.rows

        if self.color == PieceColor.WHITE:
            startrow = rows - 1
        else:
            startrow = 0
        # One-cell move.
        if (
            destinationrow == sourcerow + direction
            and destinationcol == sourcecol
        ):
            return True

        # Two-cell move from the starting row.
        return (
            sourcerow == startrow
            and destinationrow == sourcerow + (2 * direction)
            and destinationcol == sourcecol
        )

    def _is_valid_capture(
        self,
        sourcerow,
        sourcecol,
        destinationrow,
        destinationcol,
        destination_piece,
    ):
        direction = -1 if self.color == PieceColor.WHITE else 1

        return (
            destination_piece.color != self.color
            and destinationrow == sourcerow + direction
            and abs(destinationcol - sourcecol) == 1
        )
    
    def get_pathcells(
        self,
        sourcerow,
        sourcecol,
        destinationrow,
        destinationcol,
    ):
        """Return intermediate cells for a two-square pawn move.

        Returns a list with the cell the pawn passes through when moving
        two squares forward from its starting row; otherwise empty list.
        """
        if abs(destinationrow - sourcerow) == 2:
            direction = -1 if self.color == PieceColor.WHITE else 1

            return [
                (sourcerow + direction, sourcecol)
            ]

        return []