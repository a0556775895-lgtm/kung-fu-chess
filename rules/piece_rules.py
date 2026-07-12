"""Movement rules and per-kind metadata for every piece kind.

This module replaces the old per-subclass files (pawn.py, queen.py, rook.py,
bishop.py, knight.py, king.py). Instead of each kind being a `Piece`
subclass with its own `is_valid_move`/`get_path_cells`, every kind is just
a string ("P", "Q", "R", "B", "N", "K") and this module dispatches on it.

Ported 1:1 from the old files — no behavioural change, only relocation.
"""

from model.position import Position
from model.piece import PieceColor


# --- Per-kind metadata (was: constructor args in each old subclass) -------

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

ROYAL_KINDS = {"K"}


def get_move_time(kind: str) -> int:
    return MOVE_TIME[kind]


def get_jump_duration(kind: str) -> int:
    return JUMP_DURATION[kind]


def is_royal(kind: str) -> bool:
    return kind in ROYAL_KINDS


# --- Movement validation (was: is_valid_move on each subclass) ------------

def is_valid_move(
    kind: str,
    color: PieceColor,
    source: Position,
    destination: Position,
    destination_piece,
    board_rows: int = None,
) -> bool:
    """Return True if moving `kind`/`color` from source to destination
    matches that kind's movement pattern (ignores board occupancy/blocking
    beyond what each kind's own rule requires, e.g. pawn capture-vs-forward).

    `board_rows` is only required for Pawn (to know its starting row) —
    the old Pawn read this via `self.get_board().get_rows()`; here it must
    be passed in explicitly since Piece no longer holds a board reference.
    """

    if kind == "P":
        return _pawn_is_valid_move(
            color, source, destination, destination_piece, board_rows
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


def get_path_cells(kind: str, color: PieceColor, source: Position, destination: Position):
    """Return intermediate cells between source and destination as a list
    of Position, excluding source and destination themselves.

    Only kinds that can be blocked need a non-trivial path: Queen, Rook,
    Bishop, and the two-square Pawn opening move. Knight and King move in
    a single step, so their path is always empty.
    """

    if kind == "P":
        return _pawn_path_cells(color, source, destination)

    if kind == "Q":
        return _queen_path_cells(source, destination)

    if kind == "R":
        return _rook_path_cells(source, destination)

    if kind == "B":
        return _bishop_path_cells(source, destination)

    # Knight and King: single-step moves, no intermediate cells.
    return []


# --- Pawn (was: pawn.py) ---------------------------------------------------

def _pawn_is_valid_move(color, source, destination, destination_piece, board_rows):
    if destination_piece is None:
        return _pawn_is_valid_forward_move(color, source, destination, board_rows)

    return _pawn_is_valid_capture(color, source, destination, destination_piece)


def _pawn_is_valid_forward_move(color, source, destination, board_rows):
    direction = -1 if color == PieceColor.WHITE else 1

    if color == PieceColor.WHITE:
        start_row = board_rows - 1
    else:
        start_row = 0

    # One-cell move.
    if (
        destination.row == source.row + direction
        and destination.col == source.col
    ):
        return True

    # Two-cell move from the starting row.
    return (
        source.row == start_row
        and destination.row == source.row + (2 * direction)
        and destination.col == source.col
    )


def _pawn_is_valid_capture(color, source, destination, destination_piece):
    direction = -1 if color == PieceColor.WHITE else 1

    return (
        destination_piece.color != color
        and destination.row == source.row + direction
        and abs(destination.col - source.col) == 1
    )


def _pawn_path_cells(color, source, destination):
    if abs(destination.row - source.row) == 2:
        direction = -1 if color == PieceColor.WHITE else 1
        return [Position(source.row + direction, source.col)]

    return []


# --- Queen (was: queen.py) -------------------------------------------------

def _queen_is_valid_move(source, destination):
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == col_distance and row_distance > 0)
        or (row_distance == 0 and col_distance > 0)
        or (col_distance == 0 and row_distance > 0)
    )


def _queen_path_cells(source, destination):
    path = []

    row_step = (destination.row > source.row) - (destination.row < source.row)
    col_step = (destination.col > source.col) - (destination.col < source.col)

    if row_step == 0 and col_step == 0:
        return path

    row, col = source.row + row_step, source.col + col_step
    while (row, col) != (destination.row, destination.col):
        path.append(Position(row, col))
        row += row_step
        col += col_step

    return path


# --- Rook (was: rook.py) ---------------------------------------------------

def _rook_is_valid_move(source, destination):
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == 0 and col_distance > 0)
        or (col_distance == 0 and row_distance > 0)
    )


def _rook_path_cells(source, destination):
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


# --- Bishop (was: bishop.py) -----------------------------------------------

def _bishop_is_valid_move(source, destination):
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return row_distance == col_distance and row_distance > 0


def _bishop_path_cells(source, destination):
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


# --- Knight (was: knight.py) ------------------------------------------------

def _knight_is_valid_move(source, destination):
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return (
        (row_distance == 2 and col_distance == 1)
        or (row_distance == 1 and col_distance == 2)
    )


# --- King (was: king.py) ----------------------------------------------------

def _king_is_valid_move(source, destination):
    row_distance = abs(destination.row - source.row)
    col_distance = abs(destination.col - source.col)

    return max(row_distance, col_distance) == 1