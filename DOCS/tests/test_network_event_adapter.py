"""Tests for translating wire event payloads into local presentation events."""

import pytest

from networking.event_bus import EventBus
from client.network_event_adapter import NetworkEventAdapter
from networking.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from networking.models.piece import PieceColor, PieceState
from networking.models.position import Position
from networking.protocols.game import ProtocolError


def _piece(piece_id="white-pawn", color="w", state="MOVING"):
    return {"id": piece_id, "kind": "P", "color": color, "state": state}


def test_adapter_publishes_motion_and_jump_domain_events():
    bus = EventBus()
    adapter = NetworkEventAdapter(bus)
    received = []
    bus.subscribe(MotionStarted, received.append)
    bus.subscribe(JumpStarted, received.append)

    adapter.publish({
        "type": "MOTION",
        "piece": _piece(),
        "source": {"row": 6, "col": 4},
        "destination": {"row": 5, "col": 4},
        "duration_ms": 1000,
    })
    adapter.publish({
        "type": "JUMP",
        "piece": _piece(state="AIRBORNE"),
        "position": {"row": 6, "col": 4},
        "duration_ms": 5000,
    })

    motion, jump = received
    assert motion.piece.color is PieceColor.WHITE
    assert motion.source == Position(6, 4)
    assert motion.destination == Position(5, 4)
    assert motion.duration_ms == 1000
    assert jump.piece.state is PieceState.AIRBORNE
    assert jump.position == Position(6, 4)
    assert jump.duration_ms == 5000


def test_adapter_reconstructs_arrival_with_captured_piece():
    bus = EventBus()
    adapter = NetworkEventAdapter(bus)
    received = []
    bus.subscribe(Arrival, received.append)

    adapter.publish({
        "type": "ARRIVAL",
        "piece": _piece(state="LONG_REST"),
        "source": {"row": 6, "col": 4},
        "destination": {"row": 5, "col": 4},
        "captured_piece": _piece("black-pawn", "b", "CAPTURED"),
    })

    arrival = received[0].event
    assert arrival.piece.cell == Position(5, 4)
    assert arrival.captured_piece.color is PieceColor.BLACK
    assert arrival.captured_piece.state is PieceState.CAPTURED


def test_adapter_publishes_game_lifecycle_events():
    bus = EventBus()
    adapter = NetworkEventAdapter(bus)
    received = []
    bus.subscribe(GameStarted, lambda _event: received.append("started"))
    bus.subscribe(GameOver, lambda _event: received.append("over"))

    adapter.publish({"type": "GAME_STARTED"})
    adapter.publish({"type": "GAME_OVER"})

    assert received == ["started", "over"]


def test_adapter_safely_ignores_reconnect_lifecycle_until_graphical_e4():
    adapter = NetworkEventAdapter(EventBus())

    adapter.publish({"type": "PLAYER_DISCONNECTED"})
    adapter.publish({"type": "PLAYER_RECONNECTED"})


def test_adapter_exposes_observer_subscription_separately_from_proxy():
    adapter = NetworkEventAdapter()
    calls = []

    class Observer:
        def on_motion_started(self, piece, source, destination, duration_ms):
            calls.append((piece.id, source, destination, duration_ms))

        def on_jump_started(self, _piece, _position, _duration_ms):
            pass

        def on_arrival(self, _event):
            pass

        def on_game_over(self):
            pass

    cancel = adapter.subscribe(Observer())
    adapter.publish({
        "type": "MOTION",
        "piece": _piece(),
        "source": {"row": 6, "col": 4},
        "destination": {"row": 5, "col": 4},
        "duration_ms": 1000,
    })
    cancel()

    assert calls == [("white-pawn", Position(6, 4), Position(5, 4), 1000)]


def test_adapter_rejects_malformed_piece_payload():
    adapter = NetworkEventAdapter(EventBus())

    with pytest.raises(ProtocolError, match="INVALID_EVENT_PIECE"):
        adapter.publish({
            "type": "JUMP",
            "piece": _piece(color="green"),
            "position": {"row": 6, "col": 4},
            "duration_ms": 5000,
        })
