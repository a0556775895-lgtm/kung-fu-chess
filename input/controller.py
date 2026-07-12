"""Translate clicks into a selection, then into a scheduled move.

Replaces `selection_controller.py`. The old controller re-implemented
move validation locally: a friendly-fire check, a direct call to
`piece.is_valid_move`, and a direct call to `board.is_path_clear` — all
hand-rolled, and all now duplicated by `rules/rule_engine.py`. This
controller does none of that itself. It picks a `(source, destination)`
pair and delegates ALL legality checking to `rule_engine.validate_move`,
catching `RuleViolation` to decide what to do with a rejected move.

Per `ARCHITECTURE_PLAN.md` section 5's open question ("who catches the
RuleViolation exceptions?"): this module catches them. Deselection on
rejection is unconditional, same as the old controller's UX -- the only
change in step 11 is that a message is now printed too, via
`view/renderer.py`, instead of failing completely silently.

STEP 11 UPDATE: `view/renderer.py` now exists, so the TODO that used to
sit here is resolved -- `_handle_selected_click` prints a message via
`renderer.print_rule_violation(error)` before deselecting. It still does
a single `except RuleViolation` rather than branching per subclass in
this module: the per-subclass mapping to a message lives in
`renderer.py` (that's its whole job), so `controller.py` doesn't need to
know about individual `RuleViolation` subclasses at all -- only that one
was raised.
"""

from model.position import Position
from rules import piece_rules
from rules.rule_engine import validate_move, RuleViolation
from view.renderer import print_rule_violation


class Controller:
    """Track the current selection and turn clicks into scheduled moves."""

    def __init__(self, board):
        self._board = board
        self._selected_position = None

    @property
    def selected_position(self):
        return self._selected_position

    @selected_position.setter
    def selected_position(self, value):
        self._selected_position = value

    def handle_click(self, position: Position):
        if self._selected_position is None:
            self._try_select_piece(position)
        else:
            self._handle_selected_click(position)

    def _try_select_piece(self, position: Position):
        if self._board.get_piece_at(position) is not None:
            self._selected_position = position

    def _handle_selected_click(self, position: Position):
        source = self._selected_position
        clicked_piece = self._board.get_piece_at(position)
        selected_piece = self._board.get_piece_at(source)

        # Clicking a second friendly piece switches the selection instead
        # of attempting a move. Kept as a controller-level UX shortcut
        # (same behaviour as the old controller) rather than pushed into
        # rule_engine: rule_engine answers "is this move legal", not
        # "what should the UI do about a non-move click".
        if (
            clicked_piece is not None
            and clicked_piece.color == selected_piece.color
        ):
            self._selected_position = position
            return

        # STEP 11: previously a blanket `except RuleViolation: pass` with
        # a TODO to print something once a view layer existed. Now prints
        # a message specific to the exception subclass (the mapping lives
        # in `view/renderer.py`, not here) before deselecting.
        try:
            validate_move(self._board, source, position)
        except RuleViolation as error:
            print_rule_violation(error)
            self._selected_position = None
            return

        self._schedule_move(selected_piece, source, position)
        self._selected_position = None

    def _schedule_move(self, piece, source: Position, destination: Position):
        path = piece_rules.get_path_cells(piece.kind, piece.color, source, destination)
        steps = len(path) + 1
        move_time = piece_rules.get_move_time(piece.kind) * steps

        arrival_time = self._board.current_time + piece_rules.get_move_time(piece.kind)
        finish_time = self._board.current_time + move_time

        self._board.schedule_move(source, destination, arrival_time, finish_time)