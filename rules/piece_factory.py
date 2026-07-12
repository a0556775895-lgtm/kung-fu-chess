from model.piece import Piece, PieceColor

VALID_KINDS = {"P", "K", "Q", "R", "B", "N"}


class PieceFactory:

    @staticmethod
    def create_piece(token, cell=None):
        """Create a `Piece` instance from a two-char token.

        Token format: `<color><kind>`, e.g. `wP` or `bQ`.
        Raises `ValueError("UNKNOWN_TOKEN")` for unsupported kinds — same
        error contract as the old factory, so `board_parser.py` /
        `main.py`'s existing error handling doesn't need to change.

        `cell` is optional: pass it when the caller already knows where the
        piece will sit (e.g. while parsing the initial board), so the piece
        doesn't start with an unset position.
        """

        if (
            len(token) != 2
            or token[0] not in ("w", "b")
            or token[1] not in VALID_KINDS
        ):
            raise ValueError("UNKNOWN_TOKEN")

        color = PieceColor(token[0])
        kind = token[1]

        return Piece(color, kind, cell=cell)