"""Own and resolve every currently-active `Motion`.

Replaces the single `Board._pending_move` (a `PendingMove`) with a
collection: `RealTimeArbiter` holds one `Motion` per piece that is
currently mid-move, keyed by `piece.id`, so many pieces can move at once
(ARCHITECTURE_PLAN.md, section 6). `Board.click()` no longer has a
global "one move at a time" lock -- that lock is what this class exists
to make unnecessary.

Collision rule (decided): if two or more Motions become arrival-pending
for the SAME destination cell in the same `tick`, the one that was
scheduled first (registration order) wins and executes normally; every
other contender `bounce()`s -- see `motion.Motion.bounce`.

This also absorbs what used to be `Board._execute_arrival` (airborne
capture, grid placement, promotion). That logic is inherently
timing-dependent (it only makes sense at the moment a motion's
arrival_time is reached), so it lives here now rather than in
`rules/rule_engine.py`, which only ever answers "is this move legal to
*schedule*" -- see ARCHITECTURE_PLAN.md, section 7, item 1.

STEP 10 CHANGE: royal-piece capture used to be decided here (a direct
call to `Board.end_game()`). That decision now belongs to
`engine/game_engine.py` -- this class only DETECTS the capture and
reports it via `consume_royal_capture()`. See ARCHITECTURE_PLAN.md,
section 8, item 10.
"""

from model.piece import PieceColor
from rules.piece_factory import PieceFactory
from realtime.motion import Motion


class RealTimeArbiter:
    def __init__(self, board):
        self._board = board

        # dict preserves insertion order (Python 3.7+) -- this IS the
        # "first scheduled wins" collision rule; no separate timestamp
        # bookkeeping is needed for it.
        self._motions = {}

        # STEP 10: set when `_execute_arrival` sees a captured piece with
        # `is_royal() == True`. Purely a report -- this class never acts
        # on it itself. Cleared by `consume_royal_capture`.
        self._royal_captured = False

    def has_active_motion(self, piece) -> bool:
        """True if `piece` currently has a Motion in flight.

        Used by `Board.jump()` to keep its existing "don't jump a piece
        that's already committed to a regular move" guard -- now checked
        per-piece instead of via a single global pending-move slot.
        """
        return piece.id in self._motions

    def schedule(self, piece, source, destination, start_time, arrival_time, finish_time):
        """Register a new Motion for `piece` and lock it as MOVING.

        `input/controller.py` is expected to have already confirmed via
        `rule_engine.validate_move` that `piece` has no active Motion --
        this is the structural second line of defense, same rationale as
        `piece.start_move()`'s docstring.
        """
        motion = Motion(piece, source, destination, start_time, arrival_time, finish_time)
        self._motions[piece.id] = motion
        piece.start_move()
        return motion

    def tick(self, current_time):
        """Advance every active Motion to `current_time`: resolve any
        arrivals (including collisions), then any finishes."""
        self._resolve_arrivals(current_time)
        self._resolve_finishes(current_time)

    def consume_royal_capture(self) -> bool:
        """Return True if a royal piece was captured since the last call
        to this method, then clear the flag.

        STEP 10: added so `engine/game_engine.py` can poll "did a
        game-ending capture just happen?" once per `wait()` without this
        class knowing anything about what should happen in response
        (calling `Board.end_game()` is now GameEngine's job, not this
        class's). "Consume" semantics (read + clear in one call) so the
        caller doesn't need to track ticks itself.
        """
        captured = self._royal_captured
        self._royal_captured = False
        return captured

    def _resolve_arrivals(self, current_time):
        arriving = [
            motion for motion in self._motions.values()
            if motion.is_arrival_pending(current_time)
        ]

        handled = set()

        for i, motion1 in enumerate(arriving):
            if motion1.piece.id in handled:
                continue

            for motion2 in arriving[i + 1:]:
                if motion2.piece.id in handled:
                    continue

                if (
                    motion1.source == motion2.destination
                    and motion1.destination == motion2.source
                    and motion1.piece.color != motion2.piece.color
                ):
                    # motion1 הגיע ראשון כי arriving שומר על סדר הרישום
                    motion2.bounce(current_time)
                    self._execute_arrival(motion1)

                    handled.add(motion1.piece.id)
                    handled.add(motion2.piece.id)
                    break

        by_destination = {}
        for motion in arriving:
            by_destination.setdefault(motion.destination, []).append(motion)

        for contenders in by_destination.values():
            # Insertion order in `self._motions` == scheduling order, and
            # list comprehension above preserves it, so `contenders[0]` is
            # always whichever motion was scheduled first.
            winner, *losers = contenders

            for loser in losers:
                loser.bounce(current_time)

            self._execute_arrival(winner)

    def _execute_arrival(self, motion):
        piece = motion.piece
        captured_piece = self._board.get_piece_at(motion.destination)

        # Airborne-capture special case -- ported unchanged from the old
        # `Board._execute_arrival` (still an open question per
        # ARCHITECTURE_PLAN.md section 7, item 1).
        if (
            captured_piece is not None
            and captured_piece.color != piece.color
            and captured_piece.is_airborne()
        ):
            self._board.remove_piece(motion.source)
            motion.executed = True
            return

        self._board.remove_piece(motion.source)
        self._board.place_piece(motion.destination, piece)
        piece.set_cell(motion.destination)

        self._maybe_promote(piece, motion.destination)

        if captured_piece is not None and captured_piece.is_royal():
            # STEP 10 CHANGE: was `self._board.end_game()`. This class
            # now only detects and reports; `engine/game_engine.py`
            # decides what to do about it.
            self._royal_captured = True

        motion.executed = True

    def _maybe_promote(self, piece, destination):
        is_last_rank = (
            (piece.color == PieceColor.WHITE and destination.row == 0)
            or (
                piece.color == PieceColor.BLACK
                and destination.row == self._board.get_rows() - 1
            )
        )

        if piece.kind == "P" and is_last_rank:
            promoted = PieceFactory.create_piece(
                f"{piece.color.value}Q", cell=destination
            )
            self._board.place_piece(destination, promoted)

    def _resolve_finishes(self, current_time):
        finished_ids = [
            piece_id
            for piece_id, motion in self._motions.items()
            if motion.is_finish_pending(current_time)
        ]

        for piece_id in finished_ids:
            motion = self._motions.pop(piece_id)
            motion.piece.finish_move()