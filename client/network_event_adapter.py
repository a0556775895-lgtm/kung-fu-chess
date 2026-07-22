"""Translate validated network event payloads into local domain events."""

from bus.event_bus import EventBus
from engine.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from model.piece import Piece, PieceColor, PieceState
from model.position import Position
from networking.protocol import ProtocolError
from realtime.real_time_arbiter import ArrivalEvent


class NetworkEventAdapter:
    """Publish wire events on a local EventBus for existing view observers."""

    def __init__(self, bus=None):
        """Own or accept the client-local bus used only by presentation services."""
        self._bus = bus if bus is not None else EventBus()

    @property
    def bus(self) -> EventBus:
        """Expose the presentation event channel without involving the game proxy."""
        return self._bus

    def subscribe(self, observer):
        """Adapt local domain events to the existing GameObserver callbacks."""
        cancellations = [
            self._bus.subscribe(MotionStarted, lambda event: observer.on_motion_started(
                event.piece, event.source, event.destination, event.duration_ms
            )),
            self._bus.subscribe(JumpStarted, lambda event: observer.on_jump_started(
                event.piece, event.position
            )),
            self._bus.subscribe(Arrival, lambda event: observer.on_arrival(event.event)),
            self._bus.subscribe(GameOver, lambda _event: observer.on_game_over()),
        ]

        def unsubscribe() -> None:
            for cancel in cancellations:
                cancel()

        return unsubscribe

    def publish(self, payload: dict) -> None:
        """Convert one decoded EVENT payload and publish its domain equivalent."""
        event_type = payload.get("type")
        if event_type == "MOTION":
            source = _position(payload.get("source"))
            destination = _position(payload.get("destination"))
            duration_ms = payload.get("duration_ms")
            if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
                raise ProtocolError("INVALID_EVENT_DURATION")
            self._bus.publish(MotionStarted(
                _piece(payload.get("piece"), source),
                source,
                destination,
                duration_ms,
            ))
            return

        if event_type == "JUMP":
            position = _position(payload.get("position"))
            self._bus.publish(JumpStarted(
                _piece(payload.get("piece"), position),
                position,
            ))
            return

        if event_type == "ARRIVAL":
            source = _position(payload.get("source"))
            destination = _position(payload.get("destination"))
            captured_payload = payload.get("captured_piece")
            captured_piece = (
                None
                if captured_payload is None
                else _piece(captured_payload, destination)
            )
            self._bus.publish(Arrival(ArrivalEvent(
                piece=_piece(payload.get("piece"), destination),
                source=source,
                destination=destination,
                captured_piece=captured_piece,
            )))
            return

        if event_type == "GAME_STARTED":
            self._bus.publish(GameStarted())
            return

        if event_type == "GAME_OVER":
            self._bus.publish(GameOver())
            return

        raise ProtocolError("UNKNOWN_EVENT_TYPE")


def _position(payload) -> Position:
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_EVENT_POSITION")
    row = payload.get("row")
    col = payload.get("col")
    if (
        isinstance(row, bool)
        or not isinstance(row, int)
        or isinstance(col, bool)
        or not isinstance(col, int)
    ):
        raise ProtocolError("INVALID_EVENT_POSITION")
    return Position(row, col)


def _piece(payload, cell: Position) -> Piece:
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_EVENT_PIECE")
    try:
        piece_id = payload["id"]
        kind = payload["kind"]
        color = PieceColor(payload["color"])
        state = PieceState[payload["state"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError("INVALID_EVENT_PIECE") from exc
    if not isinstance(piece_id, str) or not piece_id or not isinstance(kind, str) or not kind:
        raise ProtocolError("INVALID_EVENT_PIECE")
    return Piece(piece_id, color, kind, cell, state)
