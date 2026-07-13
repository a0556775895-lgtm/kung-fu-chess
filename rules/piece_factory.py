"""Create Piece instances from two-char board-notation tokens."""

from model.piece import Piece, PieceColor

VALID_KINDS = {"P", "K", "Q", "R", "B", "N"}


class PieceFactory:
    # Sequential counter for piece ids. Reset via `reset_counter()` at
    # the start of each new board parse, so ids are deterministic
    # *per board* ("piece_0", "piece_1", ...) regardless of how many
    # other boards were parsed earlier in the same process (e.g. many
    # tests running in one pytest session).
    _next_id = 0

    @classmethod
    def reset_counter(cls):
        cls._next_id = 0

    @classmethod
    def create_piece(cls, token, cell=None):
        """Create a `Piece` instance from a two-char token.

        Token format: `<color><kind>`, e.g. `wP` or `bQ`.
        Raises `ValueError("UNKNOWN_TOKEN")` for unsupported tokens.

        `cell` is optional: pass it when the caller already knows where
        the piece will sit (e.g. while parsing the initial board).
        """

        if (
            len(token) != 2
            or token[0] not in ("w", "b")
            or token[1] not in VALID_KINDS
        ):
            raise ValueError("UNKNOWN_TOKEN")

        color = PieceColor(token[0])
        kind = token[1]

        piece_id = f"piece_{cls._next_id}"
        cls._next_id += 1

        return Piece(id=piece_id, color=color, kind=kind, cell=cell)