"""Pure text protocol for creating, joining, and cancelling rooms."""

from dataclasses import dataclass, field
import re
from typing import TypeAlias

from model.game_config import GameConfig
from networking.protocols._validation import (
    is_valid_request_id,
    is_valid_session_token,
)
from networking.serializers.game_config import (
    GameConfigSerializationError,
    GameConfigSerializer,
)


_ROOM_CODE_PATTERN = re.compile(r"[A-Z0-9]{4,12}")
_ROOM_RESPONSE_KINDS = {
    "ROOM_CREATED",
    "ROOM_JOINED",
    "ROOM_CANCELLED",
}


class RoomProtocolError(ValueError):
    """A malformed room request or response."""


@dataclass(frozen=True, slots=True)
class CreateRoomRequest:
    """Create a waiting room using the creator's preferred configuration."""

    request_id: str
    session_token: str = field(repr=False)
    requested_config: GameConfig


@dataclass(frozen=True, slots=True)
class JoinRoomRequest:
    """Join one waiting room by its public code."""

    request_id: str
    session_token: str = field(repr=False)
    room_code: str
    requested_config: GameConfig


@dataclass(frozen=True, slots=True)
class CancelRoomRequest:
    """Cancel a waiting room owned by the authenticated session."""

    request_id: str
    session_token: str = field(repr=False)
    room_code: str


@dataclass(frozen=True, slots=True)
class RoomResponse:
    """A request-correlated room lifecycle confirmation."""

    kind: str
    request_id: str
    room_code: str


RoomRequest: TypeAlias = (
    CreateRoomRequest
    | JoinRoomRequest
    | CancelRoomRequest
)


def encode_create_room(request: CreateRoomRequest) -> str:
    """Encode a room creation request and its preferred configuration."""
    _validate_common(request.request_id, request.session_token)
    return (
        f"CREATE_ROOM {request.request_id} {request.session_token} "
        f"{GameConfigSerializer.to_json(request.requested_config)}"
    )


def encode_join_room(request: JoinRoomRequest) -> str:
    """Encode a request to join an existing room."""
    _validate_common(request.request_id, request.session_token)
    _validate_room_code(request.room_code)
    return (
        f"JOIN_ROOM {request.request_id} {request.session_token} "
        f"{request.room_code} "
        f"{GameConfigSerializer.to_json(request.requested_config)}"
    )


def encode_cancel_room(request: CancelRoomRequest) -> str:
    """Encode a request to cancel a waiting room."""
    _validate_common(request.request_id, request.session_token)
    _validate_room_code(request.room_code)
    return (
        f"CANCEL_ROOM {request.request_id} "
        f"{request.session_token} {request.room_code}"
    )


def parse_room_request(message: str) -> RoomRequest:
    """Parse one room command and validate all wire-level fields."""
    if not isinstance(message, str):
        raise RoomProtocolError("MESSAGE_NOT_TEXT")

    operation = message.strip().split(maxsplit=1)[0] if message.strip() else ""
    if operation == "CREATE_ROOM":
        return _parse_create_room(message)
    if operation == "JOIN_ROOM":
        return _parse_join_room(message)
    if operation == "CANCEL_ROOM":
        return _parse_cancel_room(message)
    raise RoomProtocolError("MALFORMED_ROOM_REQUEST")


def encode_room_created(request_id: str, room_code: str) -> str:
    """Confirm that a room is waiting for its second player."""
    return _encode_response("ROOM_CREATED", request_id, room_code)


def encode_room_joined(request_id: str, room_code: str) -> str:
    """Confirm that a player joined the addressed room."""
    return _encode_response("ROOM_JOINED", request_id, room_code)


def encode_room_cancelled(request_id: str, room_code: str) -> str:
    """Confirm that the creator cancelled the addressed room."""
    return _encode_response("ROOM_CANCELLED", request_id, room_code)


def parse_room_response(message: str) -> RoomResponse:
    """Parse a room lifecycle confirmation."""
    if not isinstance(message, str):
        raise RoomProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 3 or parts[0] not in _ROOM_RESPONSE_KINDS:
        raise RoomProtocolError("MALFORMED_ROOM_RESPONSE")
    _validate_request_id(parts[1])
    _validate_room_code(parts[2])
    return RoomResponse(parts[0], parts[1], parts[2])


def _parse_create_room(message: str) -> CreateRoomRequest:
    parts = message.strip().split(maxsplit=3)
    if len(parts) != 4:
        raise RoomProtocolError("MALFORMED_CREATE_ROOM")
    _validate_common(parts[1], parts[2])
    return CreateRoomRequest(
        parts[1],
        parts[2],
        _parse_config(parts[3]),
    )


def _parse_join_room(message: str) -> JoinRoomRequest:
    parts = message.strip().split(maxsplit=4)
    if len(parts) != 5:
        raise RoomProtocolError("MALFORMED_JOIN_ROOM")
    _validate_common(parts[1], parts[2])
    _validate_room_code(parts[3])
    return JoinRoomRequest(
        parts[1],
        parts[2],
        parts[3],
        _parse_config(parts[4]),
    )


def _parse_cancel_room(message: str) -> CancelRoomRequest:
    parts = message.strip().split()
    if len(parts) != 4:
        raise RoomProtocolError("MALFORMED_CANCEL_ROOM")
    _validate_common(parts[1], parts[2])
    _validate_room_code(parts[3])
    return CancelRoomRequest(parts[1], parts[2], parts[3])


def _parse_config(payload: str) -> GameConfig:
    try:
        return GameConfigSerializer.from_json(payload)
    except GameConfigSerializationError as exc:
        raise RoomProtocolError(str(exc)) from exc


def _encode_response(kind: str, request_id: str, room_code: str) -> str:
    _validate_request_id(request_id)
    _validate_room_code(room_code)
    return f"{kind} {request_id} {room_code}"


def _validate_common(request_id: str, session_token: str) -> None:
    _validate_request_id(request_id)
    if not is_valid_session_token(session_token):
        raise RoomProtocolError("INVALID_SESSION_TOKEN")


def _validate_request_id(request_id: str) -> None:
    if not is_valid_request_id(request_id):
        raise RoomProtocolError("INVALID_REQUEST_ID")


def _validate_room_code(room_code: str) -> None:
    if (
        not isinstance(room_code, str)
        or _ROOM_CODE_PATTERN.fullmatch(room_code) is None
    ):
        raise RoomProtocolError("INVALID_ROOM_CODE")
