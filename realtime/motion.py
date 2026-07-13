"""A single piece's move currently in flight.

Per the Design Guide, section 10: arrival_time is proportional to the
number of cells crossed (N cells = N x 1000ms), and the board updates
exactly once, at arrival. There is no separate "finish" phase and no
bounce/collision-path mechanism -- same-destination collisions between
two concurrently-moving pieces are resolved by processing order in
RealTimeArbiter, not by anything this class needs to know about.
"""


class Motion:
    def __init__(self, piece, source, destination, start_time, arrival_time):
        self.piece = piece
        self.source = source
        self.destination = destination
        self.start_time = start_time
        self.arrival_time = arrival_time

    def is_arrival_pending(self, current_time) -> bool:
        return current_time >= self.arrival_time