"""Own and resolve every currently-active `Motion`.

Common route (Design Guide, section 10): one Motion per moving piece,
timed at MS_PER_CELL per cell crossed, board updated only on arrival.

Approved extension beyond the Design Guide: multiple pieces may move
simultaneously (no global "one active motion" lock / no
`motion_in_progress` rejection). `has_active_motion` therefore takes a
`piece` argument and answers "is THIS piece already moving?" -- the
per-piece guard GameEngine needs so it doesn't start a second Motion for
a piece that's already mid-move. This differs from the literal
Section-20 signature (`has_active_motion() -> bool`, no argument),
which assumed the single-motion model.

Collision rule confirmed by test cases (enemy_collision_white/black_
started_first): when two Motions of opposite color would arrive at each
other's source cell in the same tick, whichever was scheduled first
wins -- it captures normally. The other motion's piece has, by then,
already been marked CAPTURED, so its arrival is silently dropped: no
second write to the board, no double free of a cell. This falls out of
processing motions in scheduling order without any dedicated collision
code. (Same-color near-miss "stop one cell early" behavior was
described but is NOT implemented here -- explicitly out of scope for
now per direction received.)

Promotion is intentionally not implemented (Design Guide, section 3:
"Pawn has no promotion").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from model.piece import PieceState
from realtime.motion import Motion
from rules import piece_rules


@dataclass(frozen=True)
class ArrivalEvent:
    piece: object
    source: object
    destination: object
    captured_piece: object | None


@dataclass(frozen=True)
class ArrivalEvents:
    events: list = field(default_factory=list)
    king_captured: bool = False


class RealTimeArbiter:
    def __init__(self, board):
        self._board = board
        # dict preserves insertion order -- this IS the "first
        # scheduled wins" collision rule; no separate timestamp
        # bookkeeping needed for it.
        self._motions = {}
        self._airborne = {}
        self._current_time = 0
        self._royal_captured = False

    def has_active_motion(self, piece) -> bool:
        """True if `piece` currently has a Motion in flight."""
        return piece.id in self._motions

    def start_jump(self, piece) -> None:
        """Mark `piece` as airborne for 1000 ms."""
        self._airborne[piece.id] = self._current_time + 1000
        piece.state = PieceState.AIRBORNE

    def start_motion(self, piece, source, destination) -> None:
        """Register a new Motion for `piece`. Timing comes entirely
        from piece_rules.get_arrival_duration() — this class never
        branches on piece.kind itself."""
        duration = piece_rules.get_arrival_duration(piece.kind, source, destination)
        arrival_time = self._current_time + duration

        motion = Motion(piece, source, destination, self._current_time, arrival_time)
        self._motions[piece.id] = motion
        piece.state = PieceState.MOVING


    def advance_time(self, ms) -> ArrivalEvents:
        """Advance simulated time by `ms` and resolve any arrivals."""
        self._current_time += ms
        events = self._resolve_arrivals()
        self._resolve_landed()
        return ArrivalEvents(events=events, king_captured=self.consume_royal_capture())

    def _resolve_landed(self):
        """Return airborne pieces whose jump window has expired to IDLE."""
        landed = [pid for pid, land_time in self._airborne.items()
                  if self._current_time >= land_time]
        for pid in landed:
            del self._airborne[pid]
        for row in self._board.get_grid():
            for piece in row:
                if piece is not None and piece.is_airborne() and piece.id not in self._airborne:
                    piece.state = PieceState.IDLE

    def consume_royal_capture(self) -> bool:
        captured = self._royal_captured
        self._royal_captured = False
        return captured

    def _resolve_arrivals(self):
        # Motions due this tick, in scheduling order, with ties broken
        # by scheduling order too (stable sort over an insertion-
        # ordered dict keeps that guarantee).
        due_ids = [
            piece_id
            for piece_id, motion in self._motions.items()
            if motion.is_arrival_pending(self._current_time)
        ]
        due_ids.sort(key=lambda pid: self._motions[pid].arrival_time)

        events = []
        for piece_id in due_ids:
            motion = self._motions.pop(piece_id, None)
            if motion is None:  # pragma: no cover
                continue  # already resolved earlier this tick

            piece = motion.piece

            # Concurrent-collision case: this piece was captured by a
            # motion resolved earlier in this same tick (test cases
            # enemy_collision_white/black_started_first). Its own
            # arrival never happens -- drop it, don't touch the board.
            if piece.state == PieceState.CAPTURED:
                continue

            # Airborne-capture: if an enemy airborne piece occupies the
            # destination, it captures the arriving piece instead.
            destination_piece = self._board.get_piece_at(motion.destination)
            if (
                destination_piece is not None
                and destination_piece.is_airborne()
                and destination_piece.color != piece.color
            ):
                piece.state = PieceState.CAPTURED
                self._board.remove_piece(motion.source)
                if piece.kind == "K":
                    self._royal_captured = True
                events.append(
                    ArrivalEvent(piece, motion.source, motion.destination, destination_piece)
                )
                continue

            captured = self._board.move_piece(motion.source, motion.destination)
            piece.state = PieceState.IDLE

            promotion = piece_rules.get_promotion_kind(
                piece.kind, piece.color, motion.destination, self._board.rows
            )
            if promotion:
                piece.kind = promotion

            if captured is not None:
                captured.state = PieceState.CAPTURED
                if captured.kind == "K":
                    self._royal_captured = True

            events.append(
                ArrivalEvent(piece, motion.source, motion.destination, captured)
            )

        return events