"""Central move-validation logic.

Replaces the validation that used to live scattered across
`SelectionController._handle_selected_click` (friendly-fire check,
`is_valid_move` call, `is_path_clear` call) and `Board._is_path_clear`.

Deliberately depends on `BoardView` (a narrow Protocol), NOT on the
concrete `model.board.Board` class. This means:
  - Tests can validate moves against a small fake/stub object instead of
    building a full real Board.
  - This module never needs to import `model.board`, avoiding any risk of
    a circular import if Board later needs something from `rules`.

Every rejection is a distinct exception under `RuleViolation`, so callers
can either catch specific cases or do a blanket `except RuleViolation`.
"""

from typing import Optional, Protocol

from model.position import Position
from model.piece import Piece
from rules import piece_rules


# --- Narrow interface the Rule Engine needs from a board-like object ------

class BoardView(Protocol):
    """The minimal read-only surface the Rule Engine needs from a board.

    `model/board.py` will satisfy this automatically as long as it exposes
    these methods — no explicit inheritance needed (structural typing).
    """

    def get_piece_at(self, position: Position) -> Optional[Piece]:
        ...

    def is_inside_board(self, position: Position) -> bool:
        ...

    def get_rows(self) -> int:
        ...


# --- Exceptions -------------------------------------------------------------

class RuleViolation(Exception):
    """Base class for every move rejected by the Rule Engine."""


class OutOfBoardError(RuleViolation):
    """Destination cell is outside the board boundaries."""


class EmptyCellError(RuleViolation):
    """Source cell has no piece to move."""


class FriendlyFireError(RuleViolation):
    """Destination cell is occupied by a piece of the same color."""


class PieceAlreadyMovingError(RuleViolation):
    """Piece is currently mid-motion (MOVING/JUMPING) and cannot be
    selected or moved again until it finishes."""


class IllegalPatternError(RuleViolation):
    """Move does not match the piece kind's movement rules."""


class PathBlockedError(RuleViolation):
    """A piece blocks the path between source and destination."""


# --- Validation ---------------------------------------------------------

def validate_move(board: BoardView, source: Position, destination: Position) -> Position:
    """Validate a proposed move from `source` to `destination` on `board`.

    Returns `destination` if the move is legal. Raises a `RuleViolation`
    subclass on the first rule that fails — check order follows the
    original spec document:

      1. destination out of board       -> OutOfBoardError
      2. source cell empty              -> EmptyCellError
      3. destination has a friendly piece -> FriendlyFireError
      4. piece already mid-motion       -> PieceAlreadyMovingError
         (added for concurrent-moves support — not in the original doc,
         but required once multiple simultaneous motions are allowed)
      5. move doesn't match the piece's pattern -> IllegalPatternError
      6. path between source/destination is blocked -> PathBlockedError

    NOTE: this function does NOT yet handle the airborne-capture special
    case (capturing a piece mid-jump) — that rule's home is still an open
    question (see ARCHITECTURE_PLAN.md, section 7, item 1) and is
    deliberately left out until that's decided.
    """

    if not board.is_inside_board(destination):
        raise OutOfBoardError(f"{destination!r} is outside the board")

    piece = board.get_piece_at(source)
    if piece is None:
        raise EmptyCellError(f"No piece at {source!r}")

    destination_piece = board.get_piece_at(destination)

    if destination_piece is not None and destination_piece.color == piece.color:
        raise FriendlyFireError(
            f"{destination!r} is occupied by a friendly piece"
        )

    if piece.is_moving():
        raise PieceAlreadyMovingError(
            f"Piece {piece.id!r} is already mid-motion"
        )

    if not piece_rules.is_valid_move(
        piece.kind,
        piece.color,
        source,
        destination,
        destination_piece,
        board.get_rows(),
    ):
        raise IllegalPatternError(
            f"{piece.kind} cannot move from {source!r} to {destination!r}"
        )

    path = piece_rules.get_path_cells(piece.kind, piece.color, source, destination)
    for cell in path:
        if board.get_piece_at(cell) is not None:
            raise PathBlockedError(f"Path blocked at {cell!r}")

    return destination