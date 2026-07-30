"""Client-side lobby workflow between authentication and game admission."""

import asyncio
from dataclasses import dataclass
from enum import Enum
from queue import Empty, Full, Queue
import uuid

from networking.protocols.game import parse_command_response
from networking.protocols.room import (
    CancelRoomRequest,
    CreateRoomRequest,
    JoinRoomRequest,
    RoomProtocolError,
    encode_cancel_room,
    encode_create_room,
    encode_join_room,
    parse_room_response,
)

from client.transport.connection_state import ConnectionState


class StopRequested(Exception):
    """End the background lobby without reporting a transport failure."""


class LobbyActionKind(str, Enum):
    """An operation the graphical thread can request from the lobby."""

    MATCHMAKE = "MATCHMAKE"
    CREATE_ROOM = "CREATE_ROOM"
    JOIN_ROOM = "JOIN_ROOM"
    CANCEL_ROOM = "CANCEL_ROOM"


@dataclass(frozen=True, slots=True)
class LobbyAction:
    """One immutable operation handed to the asyncio transport thread."""

    kind: LobbyActionKind
    room_code: str | None = None


class LobbySession:
    """Own room state and drive one authenticated client into a game."""

    def __init__(self, transport):
        self._transport = transport
        self._actions = Queue(maxsize=1)
        self._room_code = None
        self._error = None
        self._can_cancel_room = False
        self._initial_action = LobbyAction(LobbyActionKind.MATCHMAKE)

    @property
    def room_code(self) -> str | None:
        """Return the room code while it remains relevant."""
        with self._transport._state_lock:
            return self._room_code

    @property
    def error(self) -> str | None:
        """Return the latest recoverable room-operation rejection."""
        with self._transport._state_lock:
            return self._error

    def set_initial_action(self, action: LobbyAction | None) -> None:
        """Choose whether startup stops in the lobby or enters matchmaking."""
        self._initial_action = action

    def start_matchmaking(self) -> None:
        """Ask the authenticated lobby to enter rating-based matchmaking."""
        self._queue_action(
            LobbyAction(LobbyActionKind.MATCHMAKE),
            ConnectionState.WAITING_FOR_MATCH,
        )

    def create_room(self) -> None:
        """Ask the server to create a room with this client's configuration."""
        self._queue_action(
            LobbyAction(LobbyActionKind.CREATE_ROOM),
            ConnectionState.WAITING_IN_ROOM,
        )

    def join_room(self, room_code: str) -> None:
        """Ask to join one room after validating its code synchronously."""
        try:
            encode_cancel_room(
                CancelRoomRequest(
                    "validate-room",
                    self._transport.session_token,
                    room_code,
                )
            )
        except RoomProtocolError as exc:
            raise ValueError("INVALID_ROOM_CODE") from exc
        self._queue_action(
            LobbyAction(LobbyActionKind.JOIN_ROOM, room_code),
            ConnectionState.WAITING_IN_ROOM,
        )

    def cancel_room(self) -> None:
        """Cancel a waiting room only after this client created it."""
        with self._transport._state_lock:
            if (
                self._transport._state is not ConnectionState.WAITING_IN_ROOM
                or self._room_code is None
                or not self._can_cancel_room
            ):
                raise RuntimeError("client_not_waiting_in_created_room")
            self._error = None
            room_code = self._room_code
        self._put_action(
            LobbyAction(LobbyActionKind.CANCEL_ROOM, room_code)
        )

    async def run(self, websocket):
        """Process one action at a time until the server admits a game."""
        action = self._initial_action
        self._initial_action = None
        while True:
            if action is None:
                action = await self._next_action()

            if action.kind is LobbyActionKind.MATCHMAKE:
                self._transport._set_state(
                    ConnectionState.WAITING_FOR_MATCH
                )
                return await self._transport._join(
                    websocket,
                    timeout=self._transport._match_timeout,
                )

            if action.kind is LobbyActionKind.CREATE_ROOM:
                self._transport._set_state(ConnectionState.WAITING_IN_ROOM)
                admission = await self._create_room_and_wait(websocket)
                if admission is not None:
                    return admission
                action = None
                continue

            if action.kind is LobbyActionKind.JOIN_ROOM:
                self._transport._set_state(ConnectionState.WAITING_IN_ROOM)
                admission = await self._join_room(
                    websocket,
                    action.room_code,
                )
                if admission is not None:
                    return admission
                action = None
                continue

            raise RuntimeError("UNEXPECTED_LOBBY_ACTION")

    async def _create_room_and_wait(self, websocket):
        request = CreateRoomRequest(
            f"create-room-{uuid.uuid4().hex}",
            self._transport._session_token,
            self._transport._requested_config,
        )
        await websocket.send(encode_create_room(request))
        message = await self._transport._recv_or_stop(
            websocket,
            self._transport._connect_timeout,
        )
        if self._recover_lobby_error(message, request.request_id):
            return None

        response = parse_room_response(message)
        self._validate_room_response(
            response,
            request.request_id,
            "ROOM_CREATED",
        )
        self._set_waiting_room(response.room_code)
        return await self._wait_in_created_room(
            websocket,
            response.room_code,
        )

    async def _wait_in_created_room(self, websocket, room_code: str):
        while True:
            message_task = asyncio.create_task(
                websocket.recv(),
                name=f"room-{room_code}-server",
            )
            action_task = asyncio.create_task(
                self._next_action(),
                name=f"room-{room_code}-action",
            )
            done, _ = await asyncio.wait(
                {message_task, action_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if message_task in done:
                action_task.cancel()
                await asyncio.gather(
                    action_task,
                    return_exceptions=True,
                )
                config_message = message_task.result()
                state_message = await self._transport._recv_or_stop(
                    websocket,
                    self._transport._connect_timeout,
                )
                return config_message, state_message

            message_task.cancel()
            await asyncio.gather(message_task, return_exceptions=True)
            action = action_task.result()
            if action.kind is not LobbyActionKind.CANCEL_ROOM:
                raise RuntimeError("UNEXPECTED_ROOM_WAIT_ACTION")

            cancel = CancelRoomRequest(
                f"cancel-room-{uuid.uuid4().hex}",
                self._transport._session_token,
                room_code,
            )
            await websocket.send(encode_cancel_room(cancel))
            response_message = await self._transport._recv_or_stop(
                websocket,
                self._transport._connect_timeout,
            )
            if self._recover_waiting_room_error(
                response_message,
                cancel.request_id,
            ):
                continue

            response = parse_room_response(response_message)
            self._validate_room_response(
                response,
                cancel.request_id,
                "ROOM_CANCELLED",
                room_code,
            )
            self.set_lobby()
            return None

    async def _join_room(self, websocket, room_code: str):
        request = JoinRoomRequest(
            f"join-room-{uuid.uuid4().hex}",
            self._transport._session_token,
            room_code,
            self._transport._requested_config,
        )
        await websocket.send(encode_join_room(request))
        message = await self._transport._recv_or_stop(
            websocket,
            self._transport._connect_timeout,
        )
        if self._recover_lobby_error(message, request.request_id):
            return None

        response = parse_room_response(message)
        self._validate_room_response(
            response,
            request.request_id,
            "ROOM_JOINED",
            room_code,
        )
        config_message = await self._transport._recv_or_stop(
            websocket,
            self._transport._connect_timeout,
        )
        state_message = await self._transport._recv_or_stop(
            websocket,
            self._transport._connect_timeout,
        )
        return config_message, state_message

    async def _next_action(self) -> LobbyAction:
        while not self._transport._stop_requested.is_set():
            try:
                return self._actions.get_nowait()
            except Empty:
                await asyncio.sleep(0.01)
        raise StopRequested

    def _queue_action(
        self,
        action: LobbyAction,
        waiting_state: ConnectionState,
    ) -> None:
        with self._transport._state_lock:
            if self._transport._state is not ConnectionState.LOBBY:
                raise RuntimeError("client_not_in_lobby")
            self._transport._state = waiting_state
            self._error = None
            self._room_code = (
                action.room_code
                if action.kind is LobbyActionKind.JOIN_ROOM
                else None
            )
            self._can_cancel_room = False
        try:
            self._put_action(action)
        except Exception:
            self.set_lobby()
            raise

    def _put_action(self, action: LobbyAction) -> None:
        try:
            self._actions.put_nowait(action)
        except Full as exc:
            raise RuntimeError("client_lobby_action_pending") from exc

    def _recover_lobby_error(
        self,
        message: str,
        request_id: str,
    ) -> bool:
        if not message.startswith("ERR "):
            return False
        response = parse_command_response(message)
        if response.request_id != request_id:
            raise ConnectionError("room_request_id_mismatch")
        self.set_lobby(response.reason or "room_rejected")
        return True

    def _recover_waiting_room_error(
        self,
        message: str,
        request_id: str,
    ) -> bool:
        if not message.startswith("ERR "):
            return False
        response = parse_command_response(message)
        if response.request_id != request_id:
            raise ConnectionError("room_request_id_mismatch")
        with self._transport._state_lock:
            self._error = response.reason or "room_rejected"
        return True

    @staticmethod
    def _validate_room_response(
        response,
        request_id: str,
        expected_kind: str,
        expected_room_code: str | None = None,
    ) -> None:
        if response.request_id != request_id:
            raise ConnectionError("room_request_id_mismatch")
        if response.kind != expected_kind:
            raise ConnectionError("unexpected_room_response")
        if (
            expected_room_code is not None
            and response.room_code != expected_room_code
        ):
            raise ConnectionError("room_code_mismatch")

    def set_lobby(self, error: str | None = None) -> None:
        """Reset recoverable room state and expose the idle lobby."""
        with self._transport._state_lock:
            self._transport._state = ConnectionState.LOBBY
            self._room_code = None
            self._error = error
            self._can_cancel_room = False

    def _set_waiting_room(self, room_code: str) -> None:
        with self._transport._state_lock:
            self._transport._state = ConnectionState.WAITING_IN_ROOM
            self._room_code = room_code
            self._error = None
            self._can_cancel_room = True
