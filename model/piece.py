import itertools
from enum import Enum, auto


class PieceColor(Enum):
    WHITE = "w"
    BLACK = "b"

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, PieceColor):
            return self is other
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self):
        return hash(self.value)


class PieceState(Enum):
    IDLE = auto()
    MOVING = auto()
    COOLDOWN = auto()
    JUMPING = auto()
    CAPTURED = auto()


class Piece:
    """Pure identity + runtime state for a chess piece.

    Deliberately dumb: this class knows WHO a piece is (id, color, kind)
    and WHERE/HOW it currently is (cell, state). It does NOT know how it
    is allowed to move — that logic lives in `rules/piece_rules.py`, keyed
    by `kind`. This split is what lets a single piece be looked up and
    tracked (e.g. "is this piece mid-motion?") without scanning the grid,
    which is required for concurrent moves.

    `cell` is the piece's own record of its position. `model/board.py` is
    the ONLY code allowed to mutate it (via `set_cell`) — this keeps the
    grid and the piece's self-reported position from drifting apart.
    """

    _id_counter = itertools.count(1)

    def __init__(self, color, kind: str, cell=None, id: str = None):
        if isinstance(color, str):
            color = PieceColor(color)

        self._id = id if id is not None else f"{kind}{next(Piece._id_counter)}"
        self._color = color
        self._kind = kind
        self._cell = cell
        self._state = PieceState.IDLE
        self._jump_finish_time = None

    @property
    def id(self):
        return self._id

    @property
    def color(self):
        return self._color

    @property
    def kind(self):
        return self._kind

    @property
    def cell(self):
        return self._cell

    def set_cell(self, cell):
        """Update this piece's known position.

        Intended to be called only by `model/board.py` when it moves a
        piece in the grid, so the grid and `piece.cell` never disagree.
        """
        self._cell = cell

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state: PieceState):
        self._state = new_state

    def is_moving(self):
        """True if this piece is currently mid-motion (MOVING or JUMPING).

        Used by the Rule Engine to reject re-selecting a piece that is
        already committed to a move — see PieceAlreadyMovingError.
        """
        return self._state in (PieceState.MOVING, PieceState.JUMPING)

    # --- Regular-move state management -----------------------------------
    # Mirrors start_jump/finish_jump below, but for the ordinary
    # click-to-move flow. Without this, `is_moving()` only ever returns
    # True for jumping pieces, and `PieceAlreadyMovingError` in
    # `rules/rule_engine.py` would never fire for a piece that already has
    # a regular move scheduled — a real gap once concurrent moves are
    # allowed (today it's masked by Board's single global pending-move
    # lock, but that lock is meant to go away). Board is the only caller:
    # it calls `start_move()` the moment a move is scheduled, and
    # `finish_move()` when that specific move completes.

    def start_move(self):
        """Mark this piece as mid-motion for a regular (non-jump) move."""
        self._state = PieceState.MOVING

    def finish_move(self):
        """Finish a regular move and return to IDLE.

        Guarded on the current state (only resets if still MOVING) so this
        is safe to call even if the piece's state changed in the meantime
        for some other reason (e.g. it was captured mid-flight).
        """
        if self._state == PieceState.MOVING:
            self._state = PieceState.IDLE

    # --- Jump state management (ported from the old piece.py) -----------
    # These stay on Piece because they manage runtime STATE, not movement
    # rules. `jump_duration` is kind-specific data, so it's looked up via
    # piece_rules and passed in by the caller rather than stored here.

    def start_jump(self, current_time):
        """Start a jump: set state to JUMPING and schedule finish time."""
        from rules.piece_rules import get_jump_duration

        self._state = PieceState.JUMPING
        self._jump_finish_time = current_time + get_jump_duration(self._kind)

    def finish_jump(self):
        """Finish an ongoing jump and reset state/time."""
        self._state = PieceState.IDLE
        self._jump_finish_time = None

    def is_airborne(self):
        """True if this piece is currently in the JUMPING state."""
        return self._state == PieceState.JUMPING

    def should_finish_jump(self, current_time):
        """True when a jump should finish based on `current_time`."""
        return (
            self._state == PieceState.JUMPING
            and current_time >= self._jump_finish_time
        )

    def is_royal(self):
        """True if capturing this piece ends the game.

        Default False; kind-specific override is looked up via
        `piece_rules.is_royal(self.kind)` rather than subclassing, since
        this class no longer has per-kind subclasses.
        """
        from rules.piece_rules import is_royal
        return is_royal(self._kind)

    def __str__(self):
        return f"{self._color}{self._kind}"

    def __repr__(self):
        return (
            f"Piece(id={self._id!r}, kind={self._kind!r}, "
            f"color={self._color!r}, cell={self._cell!r}, state={self._state!r})"
        )