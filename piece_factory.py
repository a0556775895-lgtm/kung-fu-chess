from king import King
from queen import Queen
from rook import Rook
from bishop import Bishop
from knight import Knight
from pawn import Pawn

class PieceFactory:

    @staticmethod
    def create_piece(token):
        """Create a `Piece` instance from a two-char token.

        Token format: `<color><type>`, e.g. `wP` or `bQ`.
        Raises `ValueError("UNKNOWN_TOKEN")` for unsupported types.
        """

        color = token[0]
        piece_type = token[1]
        if piece_type == "P":
            return Pawn(color)
        
        if piece_type == "K":
            return King(color)

        if piece_type == "Q":
            return Queen(color)

        if piece_type == "R":
            return Rook(color)

        if piece_type == "B":
            return Bishop(color)

        if piece_type == "N":
            return Knight(color)

        raise ValueError("UNKNOWN_TOKEN")