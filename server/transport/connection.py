"""Identity, authorization and bounded outbound state for one connection."""
"""מכיל את זהות החיבור,מבדיל בין צופה או שחקן, ומכיל את התור היוצא"""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from model.piece import PieceColor


class ConnectionRole(str, Enum):
    """Authorization role assigned to a connection inside one match."""

    PLAYER = "PLAYER"
    SPECTATOR = "SPECTATOR"


@dataclass
class ConnectionContext:
    """All identity, routing and backpressure state associated with one client."""

    connection_id: str
    game_id: str
    role: ConnectionRole
    color: PieceColor | None = None
    user_id: int | None = None
    username: str | None = None
    session_token: str | None = None
    websocket: Any = field(default=None, repr=False, compare=False)
    outbound: asyncio.Queue[str] = field(
        default_factory=lambda: asyncio.Queue(maxsize=256),
        repr=False,
        compare=False,
    )
    dropped_messages: int = 0

    def enqueue(self, message: str) -> None:
        """Queue without blocking; retain the newest state when a client is slow."""
        if not isinstance(message, str):
            raise TypeError("OUTBOUND_MESSAGE_NOT_TEXT")
        if self.outbound.full():
            try:
                self.outbound.get_nowait()
                self.outbound.task_done()
                self.dropped_messages += 1
            except asyncio.QueueEmpty:  # pragma: no cover - defensive race guard
                pass
        self.outbound.put_nowait(message)
