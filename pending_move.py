class PendingMove:
    """Encapsulate the state of a move that is waiting to finish."""

    def __init__(self):
        self._source = None
        self._destination = None
        self._arrival_time = None
        self._finish_time = None
        self._executed = False

    def set_move(self, source, destination, arrival_time, finish_time):
        self._source = source
        self._destination = destination
        self._arrival_time = arrival_time
        self._finish_time = finish_time
        self._executed = False

    def clear(self):
        self._source = None
        self._destination = None
        self._arrival_time = None
        self._finish_time = None
        self._executed = False

    def mark_executed(self):
        self._executed = True

    def is_arrival_pending(self, current_time):
        return (
            self._arrival_time is not None
            and not self._executed
            and current_time >= self._arrival_time
        )

    def is_finish_pending(self, current_time):
        return (
            self._finish_time is not None
            and current_time >= self._finish_time
        )

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        self._source = value

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, value):
        self._destination = value

    @property
    def arrival_time(self):
        return self._arrival_time

    @arrival_time.setter
    def arrival_time(self, value):
        self._arrival_time = value

    @property
    def finish_time(self):
        return self._finish_time

    @finish_time.setter
    def finish_time(self, value):
        self._finish_time = value

    @property
    def executed(self):
        return self._executed

    @executed.setter
    def executed(self, value):
        self._executed = value
