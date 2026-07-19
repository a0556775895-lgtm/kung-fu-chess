# תרגום מהלך גולמי (סוג כלי, מקור, יעד, לכידה) לסימון אלגברי טקסטואלי.
"""Pure formatting helpers for the moves log HUD. No cv2/Img/geometry
dependency, so these are testable in isolation from rendering.

Notation is simplified algebraic notation per CLAUDE.md: no check,
checkmate, or castling symbols (this variant has none), and no
same-kind disambiguation (e.g. two knights that can both reach the
same square would both render as "Nc6")."""

from model.position import Position
from ... import config


def _file_letter(col: int) -> str:
    """Return the file letter for a column index (0 -> 'a', 1 -> 'b', ...)."""
    return chr(ord("a") + col)


def square_name(position: Position, board_rows: int = config.BOARD_ROWS) -> str:
    """Return standard square notation (e.g. "e5") for a board Position.

    row 0 is rank `board_rows` (Black's back rank); col 0 is file 'a'.
    """
    rank = board_rows - position.row
    return f"{_file_letter(position.col)}{rank}"


def format_move(kind: str, source: Position, destination: Position,
                 is_capture: bool, board_rows: int = config.BOARD_ROWS) -> str:
    """Format a completed move as algebraic notation.

    Pawn: destination only, or "<source file>x<destination>" on capture.
    Other kinds: "<KIND>[x]<destination>".
    """
    destination_square = square_name(destination, board_rows)

    if kind == "P":
        if is_capture:
            return f"{_file_letter(source.col)}x{destination_square}"
        return destination_square

    capture_marker = "x" if is_capture else ""
    return f"{kind}{capture_marker}{destination_square}"


def format_elapsed_time(elapsed_ms: int) -> str:
    """Format elapsed milliseconds since game start as MM:SS.mmm."""
    minutes, remainder_ms = divmod(elapsed_ms, 60_000)
    seconds, millis = divmod(remainder_ms, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
