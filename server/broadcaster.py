"""Convert one Match's domain events into non-blocking outbound messages."""

from engine.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from server.protocol import encode_event


class ServerBroadcaster:
    def __init__(self, game_id, bus, connections, next_sequence, server_time_ms):
        self._game_id = game_id
        self._connections = connections
        self._next_sequence = next_sequence
        self._server_time_ms = server_time_ms
        self._cancellations = [
            bus.subscribe(MotionStarted, self._on_motion),
            bus.subscribe(JumpStarted, self._on_jump),
            bus.subscribe(Arrival, self._on_arrival),
            bus.subscribe(GameStarted, self._on_game_started),
            bus.subscribe(GameOver, self._on_game_over),
        ]

    def close(self) -> None:
        for cancel in self._cancellations:
            cancel()
        self._cancellations.clear()

    def _metadata(self, event_type: str) -> dict:
        return {
            "type": event_type,
            "game_id": self._game_id,
            "sequence": self._next_sequence(),
            "server_time_ms": self._server_time_ms(),
        }

    def _publish(self, payload: dict) -> None:
        message = encode_event(payload)
        for connection in self._connections():
            connection.enqueue(message)

    def _on_motion(self, event: MotionStarted) -> None:
        payload = self._metadata("MOTION")
        payload.update({
            "piece": _piece_payload(event.piece),
            "source": _position_payload(event.source),
            "destination": _position_payload(event.destination),
            "duration_ms": event.duration_ms,
        })
        self._publish(payload)

    def _on_jump(self, event: JumpStarted) -> None:
        payload = self._metadata("JUMP")
        payload.update({
            "piece": _piece_payload(event.piece),
            "position": _position_payload(event.position),
        })
        self._publish(payload)

    def _on_arrival(self, event: Arrival) -> None:
        arrival = event.event
        payload = self._metadata("ARRIVAL")
        payload.update({
            "piece": _piece_payload(arrival.piece),
            "source": _position_payload(arrival.source),
            "destination": _position_payload(arrival.destination),
            "captured_piece": (
                _piece_payload(arrival.captured_piece)
                if arrival.captured_piece is not None else None
            ),
        })
        self._publish(payload)

    def _on_game_started(self, _event: GameStarted) -> None:
        self._publish(self._metadata("GAME_STARTED"))

    def _on_game_over(self, _event: GameOver) -> None:
        self._publish(self._metadata("GAME_OVER"))


def _position_payload(position) -> dict[str, int]:
    return {"row": position.row, "col": position.col}


def _piece_payload(piece) -> dict[str, str]:
    return {
        "id": piece.id,
        "kind": piece.kind,
        "color": str(piece.color),
        "state": piece.state.name,
    }
