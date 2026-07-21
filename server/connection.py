"""Identity, authorization and bounded outbound state for one connection."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from model.piece import PieceColor


class ConnectionRole(str, Enum):
    PLAYER = "PLAYER"
    SPECTATOR = "SPECTATOR"


@dataclass
class ConnectionContext:
    connection_id: str
    game_id: str
    role: ConnectionRole
    color: PieceColor | None = None
    user_id: str | None = None
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
                self.dropped_messages += 1
            except asyncio.QueueEmpty:  # pragma: no cover - defensive race guard
                pass
        self.outbound.put_nowait(message)
