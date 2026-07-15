# כללי תנועה לכל סוג כלי — תקינות, תאי ביניים, תזמון הגעה והכתרה.
"""Movement rules and per-kind metadata for every piece kind.

Each public function is stateless: it receives board data and returns
a result without mutating anything. RealTimeArbiter calls only
get_arrival_duration() for timing and get_promotion_kind() for
promotion — it never branches on piece kind itself.
"""

from model.position import Position
from model.piece import PieceColor


# --- Per-kind timing (owned here, NOT in RealTimeArbiter, so the
# Arbiter never needs to branch on a piece's kind -- it only calls
# get_arrival_duration() and gets back a number). Adding a new piece
# kind with standard (steps * per-step time) timing means adding one
# entry to MOVE_TIME. Adding a kind whose movement is a flat jump
# (distance-independent, like Knight) means adding it to JUMP_DURATION
# and to JUMP_kindS as well. ---------------------------------------

MOVE_TIME = {
    "P": 1000,
    "Q": 1000,
    "R": 1000,
    "B": 1000,
    "K": 1000,
    "N": 3000,
}

JUMP_DURATION = {
    "P": 1000,
    "Q": 1000,
    "R": 1000,
    "B": 1000,
    "K": 1000,
    "N": 3000,
}

# Kinds whose movement is a flat jump rather than steps along a line --
# their duration comes straight from get_jump_duration(), with no
# multiplication by distance crossed (confirmed by tests
# knight_L_valid / knight_jumps_over_blockers: a knight jump always
# takes 3000ms regardless of the fact a knight move isn't a straight
# line of cells).
JUMP_kindS = {"N"}

ROYAL_KINDS = {"K"}

# Cooldown after arrival: a piece can't start a new move/jump while resting.
# LONG_REST follows a normal move's arrival; SHORT_REST follows a jump landing.
LONG_REST_DURATION_MS = 6000
SHORT_REST_DURATION_MS = 1000


def get_promotion_kind(kind: str, color: PieceColor, destination: Position, board_rows: int):
    """Return 'Q' if this piece should be promoted, otherwise None."""
    if kind != "P":
        return None
    promotion_row = 0 if color == PieceColor.WHITE else board_rows - 1
    return "Q" if destination.row == promotion_row else None


def get_move_time(kind: str) -> int:
    """Return the per-cell move duration in ms for a piece kind."""
    return MOVE_TIME[kind]


def get_jump_duration(kind: str) -> int:
    """Return the flat jump duration in ms for a piece kind."""
    return JUMP_DURATION[kind]


def is_royal(kind: str) -> bool:
    """Return whether kind is a royal piece (King) whose capture ends the game."""
    return kind in ROYAL_KINDS


def get_long_rest_duration() -> int:
    """Return the rest cooldown in ms after a normal move arrives."""
    return LONG_REST_DURATION_MS


def get_short_rest_duration() -> int:
    """Return the rest cooldown in ms after a jump lands."""
    return SHORT_REST_DURATION_MS


def get_arrival_duration(kind: str, source: Position, destination: Position) -> int:
    """Single timing entry point for RealTimeArbiter.

    RealTimeArbiter calls only this function -- it never branches on
    `kind` itself. Default rule (Design Guide, section 10): N cells
    crossed = N * get_move_time(kind). Kinds in JUMP_kindS instead get
    a flat get_jump_duration(kind), independent of distance.
    """
    if kind in JUMP_kindS:
        return get_jump_duration(kind)

    steps = max(
        abs(destination.row - source.row),
        abs(destination.col - source.col),
    )
    return steps * get_move_time(kind)


# --- Movement validation (was: is_valid_move on each subclass) ------------

def is_valid_move(
    kind: str,
    color: PieceColor,
    source: Position,
    destination: Position,
    destination_piece,
    boardrows: int = None,
) -> bool:
    """Return True if moving `kind`/`color` from source to destination
    matches that kind's movement pattern (ignores board occupancy/blocking
    beyond what each kind's own rule requires, e.g. pawn capture-vs-forward).

    `boardrows` is only required for Pawn (to know its starting row).
    """

    if kind == "P":
        return _pawn_is_valid_move(
            color, source, destination, destination_piece, boardrows
        )

    if kind == "Q":
        return _queen_is_valid_move(source, destination)

    if kind == "R":
        return _rook_is_valid_move(source, destination)

    if kind == "B":
        return _bishop_is_valid_move(source, destination)

    if kind == "N":
        return _knight_is_valid_move(source, destination)

    if kind == "K":
        return _king_is_valid_move(source, destination)

    raise ValueError(f"UNKNOWN_KIND: {kind}")


def get_pathcells(kind: str, color: PieceColor, source: Position, destination: Position):
    """Return intermediate cells between source and destination as a list
    of Position, excluding source and destination themselves.

    Only kinds that can be blocked need a non-trivial path: Queen, Rook,
    Bishop, and the two-square Pawn opening move. Knight and King move in
    a single step, so their path is always empty.
    """

    if kind == "P":
        return _pawn_pathcells(color, source, destination)

    if kind == "Q":
        return _queen_pathcells(source, destination)

    if kind == "R":
        return _rook_pathcells(source, destination)

    if kind == "B":
        return _bishop_pathcells(source, destination)

    # Knight and King: single-step moves, no intermediate cells.
    return []


# --- Pawn -------------------------------------------------------------

def _pawn_is_valid_move(color, source, destination, destination_piece, boardrows):
    """Validate a pawn move as a forward move (empty destination) or a diagonal capture."""
    if destination_piece is None:
        return _pawn_is_valid_forward_move(color, source, destination, boardrows)

    return _pawn_is_valid_capture(color, source, destination, destination_piece)


def _pawn_is_valid_forward_move(color, source, destination, boardrows):
    """Validate a pawn's one-cell forward move, or two-cell move from its starting row."""
    direction = -1 if color == PieceColor.WHITE else 1

    if color == PieceColor.WHITE:
        startrow = boardrows - 2
    else:
        startrow = 1

    # One-cell move.
    if (
        destination.row == source.row + direction
        and destination.col == source.col
    ):
        return True

    # Two-cell move from the starting row.
    return (
        source.row == startrow
        and destination.row == source.row + (2 * direction)
        and destination.col == source.col
    )


def _pawn_is_valid_capture(color, source, destination, destination_piece):
    """Validate a pawn's diagonal capture: one step forward-diagonal onto an enemy piece."""
    direction = -1 if color == PieceColor.WHITE else 1

    return (
        destination_piece.color != color
        and destination.row == source.row + direction
        and abs(destination.col - source.col) == 1
    )


def _pawn_pathcells(color, source, destination):
    """Return the single intermediate cell for a pawn's two-square opening move, else none."""
    if abs(destination.row - source.row) == 2:
        direction = -1 if color == PieceColor.WHITE else 1
        return [Position(source.row + direction, source.col)]

    return []


# --- Queen --------------------------------------------------------------

def _queen_is_valid_move(source, destination):
    """Validate a queen move: straight or diagonal in any direction."""
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == col_distance and row_distance > 0)
        or (row_distance == 0 and col_distance > 0)
        or (col_distance == 0 and row_distance > 0)
    )


def _queen_pathcells(source, destination):
    """Return the intermediate cells along a queen's straight or diagonal path."""
    path = []

    row_step = (destination.row > source.row) - (destination.row < source.row)
    col_step = (destination.col > source.col) - (destination.col < source.col)

    if row_step == 0 and col_step == 0:  # pragma: no cover
        return path

    row, col = source.row + row_step, source.col + col_step
    while (row, col) != (destination.row, destination.col):
        path.append(Position(row, col))
        row += row_step
        col += col_step

    return path


# --- Rook ---------------------------------------------------------------

def _rook_is_valid_move(source, destination):
    """Validate a rook move: horizontal or vertical only."""
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == 0 and col_distance > 0)
        or (col_distance == 0 and row_distance > 0)
    )


def _rook_pathcells(source, destination):
    """Return the intermediate cells along a rook's horizontal or vertical path."""
    path = []

    if source.row == destination.row:
        step = 1 if destination.col > source.col else -1
        for col in range(source.col + step, destination.col, step):
            path.append(Position(source.row, col))
    else:
        step = 1 if destination.row > source.row else -1
        for row in range(source.row + step, destination.row, step):
            path.append(Position(row, source.col))

    return path


# --- Bishop ---------------------------------------------------------------

def _bishop_is_valid_move(source, destination):
    """Validate a bishop move: diagonal only."""
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return row_distance == col_distance and row_distance > 0


def _bishop_pathcells(source, destination):
    """Return the intermediate cells along a bishop's diagonal path."""
    path = []

    row_step = 1 if destination.row > source.row else -1
    col_step = 1 if destination.col > source.col else -1

    row = source.row + row_step
    col = source.col + col_step

    while row != destination.row:
        path.append(Position(row, col))
        row += row_step
        col += col_step

    return path


# --- Knight -----------------------------------------------------------------

def _knight_is_valid_move(source, destination):
    """Validate a knight move: an L-shape (2+1 or 1+2 cells)."""
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == 2 and col_distance == 1)
        or (row_distance == 1 and col_distance == 2)
    )


# --- King ----------------------------------------------------------------

def _king_is_valid_move(source, destination):
    """Validate a king move: exactly one cell in any direction."""
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return max(row_distance, col_distance) == 1