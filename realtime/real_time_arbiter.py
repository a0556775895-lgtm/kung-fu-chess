# ניהול כל התנועות הפעילות, קידום זמן מדומה, פתרון הגעות, התנגשויות וקפיצות.
"""Owns and resolves every active Motion and airborne piece.

Timing rules:
- N cells crossed = N * 1000ms (all kinds except Knight).
- Knight always takes 3000ms regardless of distance.
- A jump lasts piece_rules.get_airborne_duration() ms; the piece stays on its cell.

Collision rule: when two enemy motions arrive at each other's source
in the same tick, the one scheduled first wins. The other piece is
already CAPTURED, so its arrival is silently dropped.

Airborne capture: if a moving enemy arrives at the cell of an airborne
piece, the arriving piece is captured and removed; the airborne piece
stays in place.

Friendly-destination rule: if a piece arrives and its destination is
occupied by a piece of the same color, it stops one cell short along
its path instead of capturing it. If that cell is also occupied, the
move is dropped and the piece stays at its source.

Promotion: applied at arrival when a pawn reaches the back rank.
"""

from __future__ import annotations

import logging

from dataclasses import dataclass, field
from model.piece import PieceState
from realtime.motion import Motion
from rules import piece_rules

logger = logging.getLogger(__name__)


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
        """Set up empty motion/airborne/resting tracking and a zeroed simulated clock for board."""
        self._board = board #TODO replace it!! real time should not know the board
        # dict preserves insertion order -- this IS the "first
        # scheduled wins" collision rule; no separate timestamp
        # bookkeeping needed for it.
        self._motions = {}
        self._airborne = {}
        self._resting = {}
        self._current_time = 0
        self._royal_captured = False

    def has_active_motion(self, piece) -> bool:
        """True if `piece` currently has a Motion in flight."""
        return piece.id in self._motions

    def start_jump(self, piece) -> None:
        """Mark `piece` as airborne for piece_rules.get_airborne_duration() ms."""
        land_time = self._current_time + piece_rules.get_airborne_duration()
        self._airborne[piece.id] = land_time
        piece.state = PieceState.AIRBORNE
        logger.debug(
            "t=%d: %s (%s) -> AIRBORNE, lands at t=%d",
            self._current_time, piece.id, piece.kind, land_time,
        )

    def start_motion(self, piece, source, destination) -> None:
        """Register a new Motion for `piece`. Timing comes entirely
        from piece_rules.get_arrival_duration() — this class never
        branches on piece.kind itself."""
        duration = piece_rules.get_arrival_duration(piece.kind, source, destination)
        arrival_time = self._current_time + duration

        motion = Motion(piece, source, destination, self._current_time, arrival_time)
        self._motions[piece.id] = motion
        piece.state = PieceState.MOVING
        logger.debug(
            "t=%d: %s (%s) -> MOVING %s -> %s, arrives at t=%d",
            self._current_time, piece.id, piece.kind, source, destination, arrival_time,
        )


    def advance_time(self, ms) -> ArrivalEvents:
        """Advance simulated time by `ms` and resolve any arrivals."""
        self._current_time += ms
        events = self._resolve_arrivals()
        self._resolve_landed()
        self._resolve_resting()
        return ArrivalEvents(events=events, king_captured=self.consume_royal_capture())

    def _resolve_landed(self):
        """Move airborne pieces whose jump window has expired into SHORT_REST."""
        landed = [pid for pid, land_time in self._airborne.items()
                  if self._current_time >= land_time]
        for pid in landed:
            del self._airborne[pid]
        for row in self._board.get_grid():
            for piece in row:
                if piece is not None and piece.is_airborne() and piece.id not in self._airborne:
                    piece.state = PieceState.SHORT_REST
                    rest_end = self._current_time + piece_rules.get_short_rest_duration()
                    self._resting[piece.id] = rest_end
                    logger.debug(
                        "t=%d: %s (%s) landed -> SHORT_REST until t=%d",
                        self._current_time, piece.id, piece.kind, rest_end,
                    )

    def _resolve_resting(self):
        """Return resting pieces whose cooldown has expired to IDLE."""
        finished = [pid for pid, end_time in self._resting.items()
                    if self._current_time >= end_time]
        for pid in finished:
            del self._resting[pid]
        for row in self._board.get_grid():
            for piece in row:
                if piece is not None and piece.is_resting() and piece.id not in self._resting:
                    piece.state = PieceState.IDLE
                    logger.debug(
                        "t=%d: %s (%s) rest finished -> IDLE",
                        self._current_time, piece.id, piece.kind,
                    )

    def consume_royal_capture(self) -> bool:
        """Return whether a king was captured since the last call, resetting the flag."""
        captured = self._royal_captured
        self._royal_captured = False
        return captured

    def _resolve_arrivals(self):
        """Resolve all motions due this tick (collisions, airborne captures, landings, promotions) and return their ArrivalEvents."""
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
                logger.debug(
                    "t=%d: %s (%s) arrival dropped -- already captured this tick (collision)",
                    self._current_time, piece.id, piece.kind,
                )
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
                logger.debug(
                    "t=%d: %s (%s) captured mid-air by airborne %s (%s) at %s",
                    self._current_time, piece.id, piece.kind,
                    destination_piece.id, destination_piece.kind, motion.destination,
                )
                events.append(
                    ArrivalEvent(piece, motion.source, motion.destination, destination_piece)
                )
                continue

            # Friendly-destination case: the target cell is occupied by a
            # piece of the same color (its motion resolved earlier this
            # tick, or it was simply resting there). Land one cell short
            # instead of capturing a friendly piece; if that cell is also
            # occupied, the move is dropped entirely and the piece stays put.
            if (
                destination_piece is not None
                and destination_piece.color == piece.color
            ):
                path = piece_rules.get_pathcells(
                    piece.kind, piece.color, motion.source, motion.destination
                )
                stop_cell = path[-1] if path else motion.source
                blocked_short = (
                    stop_cell != motion.source
                    and self._board.get_piece_at(stop_cell) is not None
                )
                if stop_cell == motion.source or blocked_short:
                    piece.state = PieceState.IDLE
                    logger.debug(
                        "t=%d: %s (%s) move to %s dropped -- friendly at destination, no room to stop short",
                        self._current_time, piece.id, piece.kind, motion.destination,
                    )
                    events.append(
                        ArrivalEvent(piece, motion.source, motion.source, None)
                    )
                    continue

                self._board.move_piece(motion.source, stop_cell)
                piece.state = PieceState.LONG_REST
                rest_end = self._current_time + piece_rules.get_long_rest_duration()
                self._resting[piece.id] = rest_end
                logger.debug(
                    "t=%d: %s (%s) stopped short at %s -> LONG_REST until t=%d -- friendly occupies %s",
                    self._current_time, piece.id, piece.kind, stop_cell, rest_end, motion.destination,
                )
                events.append(
                    ArrivalEvent(piece, motion.source, stop_cell, None)
                )
                continue

            captured = self._board.move_piece(motion.source, motion.destination)
            piece.state = PieceState.LONG_REST
            rest_end = self._current_time + piece_rules.get_long_rest_duration()
            self._resting[piece.id] = rest_end

            promotion = piece_rules.get_promotion_kind(
                piece.kind, piece.color, motion.destination, self._board.rows
            )
            if promotion:
                piece.kind = promotion

            logger.debug(
                "t=%d: %s (%s) arrived at %s -> LONG_REST until t=%d%s",
                self._current_time, piece.id, piece.kind, motion.destination, rest_end,
                f", promoted to {promotion}" if promotion else "",
            )

            if captured is not None:
                captured.state = PieceState.CAPTURED
                if captured.kind == "K":
                    self._royal_captured = True

            events.append(
                ArrivalEvent(piece, motion.source, motion.destination, captured)
            )

        return events