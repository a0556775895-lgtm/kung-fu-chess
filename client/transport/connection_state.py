"""Thread-safe presentation values for the client connection lifecycle."""

from dataclasses import dataclass
from enum import Enum


class ConnectionState(str, Enum):
    """Lifecycle states exposed safely to the graphical thread."""

    NOT_STARTED = "NOT_STARTED"
    CONNECTING = "CONNECTING"
    LOBBY = "LOBBY"
    WAITING_FOR_MATCH = "WAITING_FOR_MATCH"
    WAITING_IN_ROOM = "WAITING_IN_ROOM"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class ConnectionStatus:
    """Immutable presentation snapshot of the current transport state."""

    state: ConnectionState
    seconds_remaining: int | None = None
