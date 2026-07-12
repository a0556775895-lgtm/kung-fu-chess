from old.king import King
from old.queen import Queen
from old.rook import Rook
from old.bishop import Bishop
from old.knight import Knight
from old.pawn import Pawn
from old.piece import PieceColor

class PieceFactory:

    @staticmethod
    def create_piece(token):
        """Create a `Piece` instance from a two-char token.

        Token format: `<color><type>`, e.g. `wP` or `bQ`.
        Raises `ValueError("UNKNOWN_TOKEN")` for unsupported types.
        """

        color = PieceColor(token[0])
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