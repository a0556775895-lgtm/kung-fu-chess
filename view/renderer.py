"""Text-mode rendering: board state and rule-violation messages.

Step 11: the `view` layer now exists, so `input/controller.py`'s TODO
(catch each `RuleViolation` subclass separately and forward a specific,
readable message instead of a blanket catch-and-deselect) can finally be
resolved -- see ARCHITECTURE_PLAN.md, section 5's open question and
section 7 item 5.

Deliberately textual/abstract, per the target file tree in
ARCHITECTURE_PLAN.md section 2: `view/renderer.py` is "לוגיקת רינדור
כללית (טקסט/מופשט)". `view/image_view.py` is intentionally NOT created
in this step -- no graphics direction has been chosen yet, so it's left
for a later step once that decision is made.

STEP 11 (cont'd) -- decision: printing responsibility moves OUT of
`model/board.py` entirely, into this module. `view/` is now the single
entry point for all textual output -- both board state and rule-
violation messages -- so `Board` no longer needs to know anything about
printing at all; it only exposes data (`get_grid()`). This module wraps
`boardio.board_printer.print_board` (still the actual line-formatting
logic -- not duplicated here) rather than reimplementing it, so
`boardio/` stays the one place that knows how a grid becomes lines of
text.
"""

from boardio.board_printer import print_board as _print_grid
from rules.rule_engine import (
    RuleViolation,
    OutOfBoardError,
    EmptyCellError,
    FriendlyFireError,
    PieceAlreadyMovingError,
    IllegalPatternError,
    PathBlockedError,
)

# Keyed on the concrete exception classes from rule_engine.py, one entry
# per subclass currently defined there.
_MESSAGES = {
    OutOfBoardError: "The move goes out of bounds",
    EmptyCellError: "There is no piece at the source cell",
    FriendlyFireError: "The target cell is occupied by a friendly piece",
    PieceAlreadyMovingError: "The piece is already in motion",
    IllegalPatternError: "The move is illegal for this piece type",
    PathBlockedError: "The path to the target cell is blocked",
}


def render_rule_violation(error: RuleViolation) -> str:
    """Return a human-readable message for `error`.

    Looked up by the error's exact type. Falls back to a generic message
    built from the exception's own text for any `RuleViolation` subclass
    added later that isn't in `_MESSAGES` yet -- so forgetting to update
    this module when `rule_engine.py` grows a new exception degrades to a
    less specific message instead of crashing.
    """
    return _MESSAGES.get(type(error), f"Illegal move: {error}")


def print_rule_violation(error: RuleViolation) -> None:
    """Print a readable message for `error` to stdout."""
    print(render_rule_violation(error))


def print_board(grid) -> None:
    """Print `grid` (list of rows of Piece/None) to stdout.

    Step 11 (cont'd): this is now the only place that prints board
    state. `model/board.py` used to call `boardio.board_printer.print_board`
    directly from its own `print_board()` method -- that method is gone;
    callers (currently `engine/game_engine.py`) get the grid via
    `Board.get_grid()` and pass it here instead.
    """
    _print_grid(grid)