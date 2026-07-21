# אוסף רשומות מהלכים לכל צד — GameObserver, לא נוגע בציור.
"""Tracks every completed move, per color, for the moves log HUD.
Subscribes as a GameObserver; MovesLogRenderer reads
white_entries/black_entries off this each frame.

Timestamps use the same dt_ms clock domain as the rest of the view
layer (accumulated via tick(), fed the same dt_ms passed to
game_engine.wait()) -- not wall-clock time."""

from dataclasses import dataclass, field

from model.piece import PieceColor, PieceState
from .move_notation import format_move, format_elapsed_time


@dataclass(frozen=True)
class MoveLogEntry:
    time_str: str
    notation: str


class MovesLogData:
    """Accumulates each side's move log, one entry per completed arrival."""

    def __init__(self):
        self._entries = {PieceColor.WHITE: [], PieceColor.BLACK: []}
        self._pending_kind = {}
        self._elapsed_ms = 0

    @property
    def white_entries(self) -> list[MoveLogEntry]:
        """All of White's logged moves so far, oldest first."""
        return self._entries[PieceColor.WHITE]

    @property
    def black_entries(self) -> list[MoveLogEntry]:
        """All of Black's logged moves so far, oldest first."""
        return self._entries[PieceColor.BLACK]

    def tick(self, dt_ms: int) -> None:
        """Advance the elapsed-since-game-start clock by dt_ms."""
        self._elapsed_ms += dt_ms

    # --- GameObserver ---

    def on_motion_started(self, piece, source, destination, duration_ms) -> None:
        """Remember the piece's kind before the move -- RealTimeArbiter
        applies pawn promotion to piece.kind at arrival, so this is the
        only point where the pre-promotion kind is still visible."""
        self._pending_kind[piece.id] = piece.kind

    def on_arrival(self, event) -> None:
        """Log a completed move, unless the mover was captured mid-air
        (airborne capture -- no move actually completed) or the move was
        fully dropped (friendly-blocked with no room to stop short,
        event.source == event.destination)."""
        kind = self._pending_kind.pop(event.piece.id, event.piece.kind)

        if event.piece.state == PieceState.CAPTURED:
            return
        if event.source == event.destination:
            return

        is_capture = event.captured_piece is not None
        notation = format_move(kind, event.source, event.destination, is_capture)
        entry = MoveLogEntry(time_str=format_elapsed_time(self._elapsed_ms), notation=notation)
        self._entries[event.piece.color].append(entry)

    def on_jump_started(self, piece, position) -> None:
        """No-op: jumps don't change cell, so there's nothing to log
        as an algebraic move (and RealTimeArbiter never fires on_arrival
        for a jump landing anyway)."""
        pass

    def on_game_over(self) -> None:
        """No-op: the log is already complete by the time the game ends."""
        pass
