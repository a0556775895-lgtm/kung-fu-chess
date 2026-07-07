from king import King
from Queen import Queen
from Rook import Rook
from Bishop import Bishop
from Knight import Knight
from Pawn import Pawn

class PieceFactory:

    @staticmethod
    def create_piece(token):
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