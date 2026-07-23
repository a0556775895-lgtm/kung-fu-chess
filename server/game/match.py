"""One isolated authoritative game and its assigned connections."""
"""מייצגת משחק בודד"""
from dataclasses import replace
from datetime import datetime, timezone

from networking.protocol import encode_state
from server.game.game_result import FinishReason, GameResult
from server.transport.broadcaster import ServerBroadcaster


class Match:
    """Isolate one authoritative engine, sequence stream and connection group."""

    def __init__(self, game_id: str, engine, game_config=None, now=None):
        """Create one game boundary and attach its per-match event broadcaster."""
        if not game_id:
            raise ValueError("INVALID_GAME_ID")
        self.game_id = game_id
        self.engine = engine
        self.game_config = game_config
        self._connections = {}
        self._sequence = 0
        self._result = None
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.broadcaster = ServerBroadcaster(
            game_id=game_id,
            bus=engine.bus,
            connections=self.connections,
            next_sequence=self.next_sequence,
            server_time_ms=self.server_time_ms,
        )

    def add_connection(self, context) -> None:
        """Attach a unique connection that is already assigned to this game id."""
        if context.game_id != self.game_id:
            raise ValueError("CONNECTION_GAME_MISMATCH")
        if context.connection_id in self._connections:
            raise ValueError("CONNECTION_ALREADY_EXISTS")
        self._connections[context.connection_id] = context

    def remove_connection(self, connection_id: str):
        """Detach a connection, returning it when it was registered."""
        return self._connections.pop(connection_id, None)

    def has_connection(self, context) -> bool:
        """Check identity, not only id equality, to reject forged contexts."""
        return self._connections.get(context.connection_id) is context

    def connections(self) -> tuple:
        """Return a stable snapshot for synchronous broadcasting."""
        return tuple(self._connections.values())

    def next_sequence(self) -> int:
        """Allocate the next ordering number shared by STATE and EVENT messages."""
        self._sequence += 1
        return self._sequence

    def server_time_ms(self) -> int:
        """Read the single authoritative clock from the engine snapshot."""
        return self.engine.snapshot().server_time_ms

    def snapshot_for(self, context, sequence: int | None = None):
        """Add connection-specific role, color and routing metadata to a snapshot."""
        if not self.has_connection(context):
            raise ValueError("CONNECTION_NOT_REGISTERED")
        base = self.engine.snapshot()
        return replace(
            base,
            player_names=self._player_names(),
            game_id=self.game_id,
            role=context.role.value,
            assigned_color=str(context.color) if context.color is not None else None,
            sequence=self._sequence if sequence is None else sequence,
        )

    def _player_names(self) -> dict[str, str]:
        """Map assigned colors to display names, retaining labels for empty seats."""
        names = {"w": "White", "b": "Black"}
        for connection in self.connections():
            if connection.color is not None and connection.username is not None:
                names[str(connection.color)] = connection.username
        return names

    def send_state(self, context) -> None:
        """Queue a fresh full STATE for one registered connection."""
        sequence = self.next_sequence()
        context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def broadcast_state(self) -> None:
        """Queue the same ordered game state for every connection in this Match."""
        sequence = self.next_sequence()
        for context in self.connections():
            context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def advance_time(self, milliseconds: int) -> None:
        """Advance this Match and convert a king capture into one final result."""
        if milliseconds < 0:
            raise ValueError("NEGATIVE_TICK")
        self.engine.wait(milliseconds)
        if self.engine.game_over and self._result is None:
            if self.engine.winner_color is None:
                raise RuntimeError("GAME_OVER_WITHOUT_WINNER")
            self.finish(GameResult(
                winner_color=self.engine.winner_color,
                reason=FinishReason.KING_CAPTURE,
                ended_at=self._now(),
            ))

    def finish(self, result: GameResult) -> bool:
        """Store the first final result and ignore repeated finish attempts."""
        if not isinstance(result, GameResult):
            raise ValueError("INVALID_GAME_RESULT")
        if self._result is not None:
            return False
        self._result = result
        return True

    @property
    def result(self) -> GameResult | None:
        """Return the immutable final result, or None while the game is active."""
        return self._result

    def close(self) -> None:
        """Unsubscribe the broadcaster and release all connection references."""
        self.broadcaster.close()
        self._connections.clear()
