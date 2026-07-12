"""A single piece's move currently in flight.

Conceptually the successor to `pending_move.PendingMove` (same fields:
source, destination, arrival_time, finish_time, executed) but instances
are meant to coexist: `realtime/real_time_arbiter.py` holds a whole
collection of these -- one per piece with an active move -- instead of
`Board` holding a single one. See ARCHITECTURE_PLAN.md, section 6.
"""


class Motion:
    """One piece's move, from scheduling to completion (or a lost
    collision, see `bounce`).

    `arrival_time` is when the piece would occupy `destination` in the
    grid -- a single "hop" delay, the same duration regardless of how many
    cells the path crosses (ported unchanged from the old timing model in
    `pending_move.py` / `selection_controller.py`). `finish_time` is when
    the piece's MOVING lock is released and it becomes selectable again,
    proportional to the full path length.
    """

    def __init__(self, piece, source, destination, start_time, arrival_time, finish_time):
        self.piece = piece
        self.source = source
        self.destination = destination
        self.start_time = start_time
        self.arrival_time = arrival_time
        self.finish_time = finish_time
        self.executed = False
        self.bounced = False

    def is_arrival_pending(self, current_time):
        return not self.executed and current_time >= self.arrival_time

    def is_finish_pending(self, current_time):
        return current_time >= self.finish_time

    def travel_duration(self):
        """Duration of the forward leg: scheduling time -> arrival time."""
        return self.arrival_time - self.start_time

    def bounce(self, current_time):
        """Lose a same-destination collision: never occupy `destination`.

        Decision: a lost motion "travels there and back" -- it never
        actually occupies the contested cell, but its MOVING lock is
        extended by another `travel_duration()` (the return trip) before
        it's released. No grid change is needed for the bounce itself:
        the piece was always still physically at `source` in the grid up
        to this point (Board only writes the grid on a successful
        arrival, in `RealTimeArbiter._execute_arrival`), so there is
        nothing to revert.
        """
        duration = self.travel_duration()
        self.arrival_time = current_time + duration
        self.finish_time = current_time + duration
        self.executed = True  # the forward arrival is permanently skipped
        self.bounced = True