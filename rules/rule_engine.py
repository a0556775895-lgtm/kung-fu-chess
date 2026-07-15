# אימות חוקיות מהלך מבוקש — קריאה בלבד מהלוח, מחזיר MoveValidation.
from dataclasses import dataclass
from typing import Optional, Protocol

from model.position import Position
from model.piece import Piece
from rules import piece_rules


class BoardView(Protocol):
    """Read-only board interface required by RuleEngine."""

    @property
    def rows(self) -> int:
        ...

    def get_piece_at(self, position: Position) -> Optional[Piece]:
        ...

    def is_inside_board(self, position: Position) -> bool:
        ...


@dataclass(frozen=True)
class MoveValidation:
    """Result of a legality check.

    reason is always set: 'ok' on success, or one of:
    'outside_board', 'empty_source', 'friendly_destination', 'illegal_piece_move'.
    A blocked sliding path is reported as 'illegal_piece_move'.
    """

    is_valid: bool
    reason: str


class RuleEngine:
    """Validates a requested move against the game rules.

    Read-only with respect to Board: never moves pieces or updates state.
    Does not check game_over or whether a piece is already moving —
    those guards are owned by GameEngine.
    """

    @staticmethod
    def validate_move(
        board: BoardView,
        source: Position,
        destination: Position,
    ) -> MoveValidation:
        """Check that a move from source to destination is legal (bounds, occupancy, piece pattern, clear path)."""

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