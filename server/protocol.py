"""Pure text protocol parsing and encoding for multiplayer messages."""

from dataclasses import dataclass
import json
import re
from typing import Any

from engine.snapshot import GameSnapshot
from model.position import Position
from networking.snapshot_serializer import GameSnapshotSerializer


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_MOVE_RE = re.compile(r"^(?P<color>[WB])(?P<kind>[PNBRQK])(?P<src>[a-h][1-8])(?P<dst>[a-h][1-8])$")
_JUMP_RE = re.compile(r"^(?P<color>[WB])(?P<kind>[PNBRQK])(?P<src>[a-h][1-8])$")


class ProtocolError(ValueError):
    """A malformed or unsupported wire message."""


@dataclass(frozen=True)
class MoveCommand:
    request_id: str
    color: str
    kind: str
    source: Position
    destination: Position


@dataclass(frozen=True)
class JumpCommand:
    request_id: str
    color: str
    kind: str
    source: Position


@dataclass(frozen=True)
class CommandResponse:
    request_id: str
    accepted: bool
    reason: str | None = None


ClientCommand = MoveCommand | JumpCommand


def parse_client_command(message: str) -> ClientCommand:
    if not isinstance(message, str):
        raise ProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 3:
        raise ProtocolError("MALFORMED_COMMAND")

    command_name, request_id, piece_token = parts
    _validate_request_id(request_id)

    if command_name == "MOVE":
        match = _MOVE_RE.fullmatch(piece_token)
        if match is None:
            raise ProtocolError("MALFORMED_MOVE")
        return MoveCommand(
            request_id=request_id,
            color=match["color"],
            kind=match["kind"],
            source=algebraic_to_position(match["src"]),
            destination=algebraic_to_position(match["dst"]),
        )

    if command_name == "JUMP":
        match = _JUMP_RE.fullmatch(piece_token)
        if match is None:
            raise ProtocolError("MALFORMED_JUMP")
        return JumpCommand(
            request_id=request_id,
            color=match["color"],
            kind=match["kind"],
            source=algebraic_to_position(match["src"]),
        )

    raise ProtocolError("UNKNOWN_COMMAND")


def encode_move(command: MoveCommand) -> str:
    _validate_request_id(command.request_id)
    token = (
        f"{command.color}{command.kind}"
        f"{position_to_algebraic(command.source)}"
        f"{position_to_algebraic(command.destination)}"
    )
    if _MOVE_RE.fullmatch(token) is None:
        raise ProtocolError("INVALID_MOVE")
    return f"MOVE {command.request_id} {token}"


def encode_jump(command: JumpCommand) -> str:
    _validate_request_id(command.request_id)
    token = f"{command.color}{command.kind}{position_to_algebraic(command.source)}"
    if _JUMP_RE.fullmatch(token) is None:
        raise ProtocolError("INVALID_JUMP")
    return f"JUMP {command.request_id} {token}"


def encode_ok(request_id: str) -> str:
    _validate_request_id(request_id)
    return f"OK {request_id}"


def encode_error(request_id: str, reason: str) -> str:
    _validate_request_id(request_id)
    if not reason or any(character.isspace() for character in reason):
        raise ProtocolError("INVALID_ERROR_REASON")
    return f"ERR {request_id} {reason}"


def parse_command_response(message: str) -> CommandResponse:
    parts = message.strip().split()
    if len(parts) == 2 and parts[0] == "OK":
        _validate_request_id(parts[1])
        return CommandResponse(parts[1], True)
    if len(parts) == 3 and parts[0] == "ERR":
        _validate_request_id(parts[1])
        return CommandResponse(parts[1], False, parts[2])
    raise ProtocolError("MALFORMED_RESPONSE")


def encode_state(snapshot: GameSnapshot) -> str:
    return f"STATE {GameSnapshotSerializer.to_json(snapshot)}"


def decode_state(message: str) -> GameSnapshot:
    prefix = "STATE "
    if not message.startswith(prefix):
        raise ProtocolError("NOT_STATE_MESSAGE")
    return GameSnapshotSerializer.from_json(message[len(prefix):])


def encode_event(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_EVENT")
    return "EVENT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def decode_event(message: str) -> dict[str, Any]:
    prefix = "EVENT "
    if not message.startswith(prefix):
        raise ProtocolError("NOT_EVENT_MESSAGE")
    try:
        payload = json.loads(message[len(prefix):])
    except json.JSONDecodeError as exc:
        raise ProtocolError("INVALID_EVENT_JSON") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("INVALID_EVENT")
    return payload


def algebraic_to_position(square: str) -> Position:
    if not isinstance(square, str) or re.fullmatch(r"[a-h][1-8]", square) is None:
        raise ProtocolError("INVALID_SQUARE")
    col = ord(square[0]) - ord("a")
    row = 8 - int(square[1])
    return Position(row, col)


def position_to_algebraic(position: Position) -> str:
    if not isinstance(position, Position) or not (0 <= position.row < 8 and 0 <= position.col < 8):
        raise ProtocolError("INVALID_POSITION")
    return f"{chr(ord('a') + position.col)}{8 - position.row}"


def _validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise ProtocolError("INVALID_REQUEST_ID")
