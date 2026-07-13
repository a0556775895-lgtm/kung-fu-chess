from dataclasses import dataclass
from typing import Optional, Protocol

from model.position import Position
from model.piece import Piece
from rules import piece_rules


class BoardView(Protocol):
    """Read-only interface required by RuleEngine."""

    @property
    def rows(self) -> int:
        ...

    def get_piece_at(self, position: Position) -> Optional[Piece]:
        ...

    def is_inside_board(self, position: Position) -> bool:
        ...


@dataclass(frozen=True)
class MoveValidation:
    """Result of a legality check (Design Guide, section 8).

    `reason` is always present: "ok" for a valid move, otherwise a
    stable machine-readable string such as "outside_board",
    "empty_source", "friendly_destination", or "illegal_piece_move".
    A blocked sliding path is reported as "illegal_piece_move" too --
    the Design Guide defines only these four failure reasons, and from
    the caller's perspective "blocked" and "wrong pattern" both mean
    "this piece cannot make this move right now".
    """

    is_valid: bool
    reason: str


class RuleEngine:
    """Validates moves according to the game rules.

    Read-only with respect to Board: inspects state and returns a
    MoveValidation, but never moves pieces, removes captures, starts
    motions, or updates game state. It also does not know about
    game_over or about whether a piece already has an active Motion --
    those are application-level guards owned by GameEngine and checked
    *before* GameEngine calls here (Design Guide, section 9).
    """

    @staticmethod
    def validate_move(
        board: BoardView,
        source: Position,
        destination: Position,
    ) -> MoveValidation:

        if not board.is_inside_board(source) or not board.is_inside_board(destination):
            return MoveValidation(is_valid=False, reason="outside_board")

        piece = board.get_piece_at(source)
        if piece is None:
            return MoveValidation(is_valid=False, reason="empty_source")

        destination_piece = board.get_piece_at(destination)

        if (
            destination_piece is not None
            and destination_piece.color == piece.color
        ):
            return MoveValidation(is_valid=False, reason="friendly_destination")

        if not piece_rules.is_valid_move(
            piece.kind,
            piece.color,
            source,
            destination,
            destination_piece,
            board.rows,
        ):
            return MoveValidation(is_valid=False, reason="illegal_piece_move")

        if not RuleEngine.is_path_clear(board, piece, source, destination):
            return MoveValidation(is_valid=False, reason="illegal_piece_move")

        return MoveValidation(is_valid=True, reason="ok")

    @staticmethod
    def is_path_clear(
        board: BoardView,
        piece: Piece,
        source: Position,
        destination: Position,
    ) -> bool:
        """Return whether the path between two cells is clear."""

        path = piece_rules.get_pathcells(
            piece.kind,
            piece.color,
            source,
            destination,
        )

        return all(
            board.get_piece_at(cell) is None
            for cell in path
        )