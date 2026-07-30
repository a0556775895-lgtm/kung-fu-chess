"""Client-side adapter from the existing engine-shaped API to wire messages."""

from dataclasses import replace
import math
import time
import uuid

from engine.snapshot import GameSnapshot
from model.position import Position
from networking.protocols.game import (
    JumpCommand,
    MoveCommand,
    ProtocolError,
    decode_event,
    decode_state,
    encode_jump,
    encode_move,
    parse_command_response,
)

from .snapshot_board_view import SnapshotBoardView


class RemoteGameEngineProxy:
    """Represent one remote authoritative game to synchronous client code."""

    def __init__(self, network_client, request_id_factory=None):
        """Start from the validated handshake snapshot held by NetworkClient."""
        initial_state = network_client.initial_state
        if initial_state.role not in {"PLAYER", "SPECTATOR"}:
            raise ValueError("GAME_ROLE_REQUIRED")
        if (
            initial_state.role == "PLAYER"
            and initial_state.assigned_color not in {"w", "b"}
        ):
            raise ValueError("PLAYER_COLOR_REQUIRED")
        if (
            initial_state.role == "SPECTATOR"
            and initial_state.assigned_color is not None
        ):
            raise ValueError("SPECTATOR_COLOR_FORBIDDEN")
        if not initial_state.game_id:
            raise ValueError("GAME_ID_REQUIRED")

        self._network_client = network_client
        self._request_id_factory = request_id_factory or (
            lambda prefix: f"{prefix}-{uuid.uuid4().hex}"
        )
        self._board = SnapshotBoardView(initial_state)
        self._role = initial_state.role
        self._assigned_color = initial_state.assigned_color
        self._game_id = initial_state.game_id
        self._last_sequence = initial_state.sequence
        self._responses = {}
        self._events = []
        self._disconnected_player_deadlines = {}

    @property
    def board(self) -> SnapshotBoardView:
        """Return the read-only board facade used by the existing Controller."""
        return self._board

    @property
    def assigned_color(self) -> str | None:
        """Return the assigned player side, or None while spectating."""
        return self._assigned_color

    @property
    def can_control(self) -> bool:
        """Whether this remote participant owns a movable player side."""
        return self._role == "PLAYER"

    @property
    def opponent_reconnect_seconds(self) -> int | None:
        """Return the local countdown for a server-reported opponent disconnect."""
        if not self._disconnected_player_deadlines:
            return None
        return max(
            0,
            min(
                math.ceil(deadline - time.monotonic())
                for deadline in self._disconnected_player_deadlines.values()
            ),
        )

    def snapshot(self, selected_cell: Position | None = None) -> GameSnapshot:
        """Return the newest server state with local-only selection metadata."""
        return replace(self._board.snapshot, selected_cell=selected_cell)

    def request_move(self, source: Position, destination: Position) -> str | None:
        """Queue MOVE for an owned source piece and return its request id."""
        if not self.can_control or not self._network_client.is_connected:
            return None
        piece = self._owned_piece_at(source)
        if piece is None:
            return None
        request_id = self._request_id_factory("move")
        self._network_client.send(
            encode_move(
                MoveCommand(
                    request_id=request_id,
                    color=self._assigned_color.upper(),
                    kind=piece.kind.upper(),
                    source=source,
                    destination=destination,
                )
            )
        )
        return request_id

    def request_jump(self, source: Position) -> str | None:
        """Queue JUMP for an owned source piece and return its request id."""
        if not self.can_control or not self._network_client.is_connected:
            return None
        piece = self._owned_piece_at(source)
        if piece is None:
            return None
        request_id = self._request_id_factory("jump")
        self._network_client.send(
            encode_jump(
                JumpCommand(
                    request_id=request_id,
                    color=self._assigned_color.upper(),
                    kind=piece.kind.upper(),
                    source=source,
                )
            )
        )
        return request_id

    def process_network_messages(self) -> int:
        """Apply every queued server message and return how many were consumed."""
        messages = self._network_client.drain_messages()
        for message in messages:
            self._process_message(message)
        return len(messages)

    def pop_response(self, request_id: str):
        """Remove and return a correlated OK/ERR response, if one arrived."""
        return self._responses.pop(request_id, None)

    def drain_events(self) -> list[dict]:
        """Return ordered event payloads for the presentation adapter in B4.3."""
        events = self._events
        self._events = []
        return events

    def _owned_piece_at(self, position: Position):
        piece = self._board.get_piece_at(position)
        if piece is None or piece.color != self._assigned_color:
            return None
        return piece

    def _process_message(self, message: str) -> None:
        if message.startswith("STATE "):
            state = decode_state(message)
            if self._accept_ordered(state.game_id, state.sequence):
                self._board.update(state)
            return

        if message.startswith("EVENT "):
            event = decode_event(message)
            if self._accept_ordered(event.get("game_id"), event.get("sequence")):
                self._track_connection_lifecycle(event)
                self._events.append(event)
            return

        if message.startswith(("OK ", "ERR ")):
            response = parse_command_response(message)
            self._responses[response.request_id] = response
            return

        raise ProtocolError("UNEXPECTED_SERVER_MESSAGE")

    def _track_connection_lifecycle(self, event: dict) -> None:
        """Track only opponent lifecycle events needed by the graphical overlay."""
        event_type = event.get("type")
        if event_type == "GAME_OVER":
            self._disconnected_player_deadlines.clear()
            return
        color = event.get("color")
        if color == self._assigned_color:
            return
        if event_type == "PLAYER_DISCONNECTED":
            grace = event.get("grace_period_seconds")
            if (
                isinstance(grace, bool)
                or not isinstance(grace, (int, float))
                or not math.isfinite(grace)
                or grace < 0
            ):
                raise ProtocolError("INVALID_RECONNECT_GRACE_PERIOD")
            self._disconnected_player_deadlines[color] = (
                time.monotonic() + grace
            )
        elif event_type == "PLAYER_RECONNECTED":
            self._disconnected_player_deadlines.pop(color, None)

    def _accept_ordered(self, game_id, sequence) -> bool:
        if game_id != self._game_id:
            raise ProtocolError("GAME_ID_MISMATCH")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ProtocolError("INVALID_SEQUENCE")
        if sequence <= self._last_sequence:
            return False
        self._last_sequence = sequence
        return True
