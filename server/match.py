"""One isolated authoritative game and its assigned connections."""

from dataclasses import replace

from server.broadcaster import ServerBroadcaster
from server.protocol import encode_state


class Match:
    def __init__(self, game_id: str, engine):
        if not game_id:
            raise ValueError("INVALID_GAME_ID")
        self.game_id = game_id
        self.engine = engine
        self._connections = {}
        self._sequence = 0
        self.broadcaster = ServerBroadcaster(
            game_id=game_id,
            bus=engine.bus,
            connections=self.connections,
            next_sequence=self.next_sequence,
            server_time_ms=self.server_time_ms,
        )

    def add_connection(self, context) -> None:
        if context.game_id != self.game_id:
            raise ValueError("CONNECTION_GAME_MISMATCH")
        if context.connection_id in self._connections:
            raise ValueError("CONNECTION_ALREADY_EXISTS")
        self._connections[context.connection_id] = context

    def remove_connection(self, connection_id: str):
        return self._connections.pop(connection_id, None)

    def has_connection(self, context) -> bool:
        return self._connections.get(context.connection_id) is context

    def connections(self) -> tuple:
        return tuple(self._connections.values())

    def next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def server_time_ms(self) -> int:
        return self.engine.snapshot().server_time_ms

    def snapshot_for(self, context, sequence: int | None = None):
        if not self.has_connection(context):
            raise ValueError("CONNECTION_NOT_REGISTERED")
        base = self.engine.snapshot()
        return replace(
            base,
            game_id=self.game_id,
            role=context.role.value,
            assigned_color=str(context.color) if context.color is not None else None,
            sequence=self._sequence if sequence is None else sequence,
        )

    def send_state(self, context) -> None:
        sequence = self.next_sequence()
        context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def broadcast_state(self) -> None:
        sequence = self.next_sequence()
        for context in self.connections():
            context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def advance_time(self, milliseconds: int) -> None:
        if milliseconds < 0:
            raise ValueError("NEGATIVE_TICK")
        self.engine.wait(milliseconds)

    def close(self) -> None:
        self.broadcaster.close()
        self._connections.clear()
