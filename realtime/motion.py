# ייצוג תנועה בודדת של כלי אחד בזמן ריצה.
"""A single in-flight piece move.

Holds the piece, source, destination, start time, and arrival time.
The board is updated exactly once, at arrival. Collision resolution
is handled by RealTimeArbiter, not here.
"""


class Motion:
    def __init__(self, piece, source, destination, start_time, arrival_time):
        """Store the piece and the timing/endpoints of its in-flight move."""
        self.piece = piece
        self.source = source
        self.destination = destination
        self.start_time = start_time
        self.arrival_time = arrival_time

    def is_arrival_pending(self, current_time) -> bool:
        """Return True if the piece has reached or passed its arrival time."""
        return current_time >= self.arrival_time