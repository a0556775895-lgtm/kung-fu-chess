"""Round-trip and validation tests for the room wire protocol."""

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocols.room import (
    CancelRoomRequest,
    CreateRoomRequest,
    JoinRoomRequest,
    RoomProtocolError,
    encode_cancel_room,
    encode_create_room,
    encode_join_room,
    encode_room_cancelled,
    encode_room_created,
    encode_room_joined,
    parse_room_request,
    parse_room_response,
)


TOKEN = "session-token"


@pytest.mark.parametrize(
    "room_request,encoder",
    [
        (
            CreateRoomRequest("create-1", TOKEN, STANDARD_GAME_CONFIG),
            encode_create_room,
        ),
        (
            JoinRoomRequest("join-1", TOKEN, "AB12", STANDARD_GAME_CONFIG),
            encode_join_room,
        ),
        (
            CancelRoomRequest("cancel-1", TOKEN, "AB12"),
            encode_cancel_room,
        ),
    ],
)
def test_room_requests_round_trip_without_exposing_tokens(room_request, encoder):
    assert parse_room_request(encoder(room_request)) == room_request
    assert TOKEN not in repr(room_request)


@pytest.mark.parametrize(
    "message,reason",
    [
        (None, "MESSAGE_NOT_TEXT"),
        ("", "MALFORMED_ROOM_REQUEST"),
        ("ROOM_LIST req token", "MALFORMED_ROOM_REQUEST"),
        ("CREATE_ROOM req token", "MALFORMED_CREATE_ROOM"),
        ("CREATE_ROOM bad/id token {}", "INVALID_REQUEST_ID"),
        ("CREATE_ROOM req invalid+token {}", "INVALID_SESSION_TOKEN"),
        ("CREATE_ROOM req token {}", "INVALID_GAME_CONFIG_FIELDS"),
        ("JOIN_ROOM req token AB12", "MALFORMED_JOIN_ROOM"),
        ("JOIN_ROOM req token bad! {}", "INVALID_ROOM_CODE"),
        ("JOIN_ROOM req token AB12 nope", "INVALID_GAME_CONFIG_JSON"),
        ("CANCEL_ROOM req token", "MALFORMED_CANCEL_ROOM"),
        ("CANCEL_ROOM req token bad!", "INVALID_ROOM_CODE"),
    ],
)
def test_room_request_parser_rejects_malformed_messages(message, reason):
    with pytest.raises(RoomProtocolError, match=reason):
        parse_room_request(message)


@pytest.mark.parametrize(
    "encoder,kind",
    [
        (encode_room_created, "ROOM_CREATED"),
        (encode_room_joined, "ROOM_JOINED"),
        (encode_room_cancelled, "ROOM_CANCELLED"),
    ],
)
def test_room_responses_round_trip(encoder, kind):
    response = parse_room_response(encoder("request-1", "AB12"))

    assert response.kind == kind
    assert response.request_id == "request-1"
    assert response.room_code == "AB12"


@pytest.mark.parametrize(
    "message,reason",
    [
        (None, "MESSAGE_NOT_TEXT"),
        ("ROOM_CREATED request-1", "MALFORMED_ROOM_RESPONSE"),
        ("UNKNOWN request-1 AB12", "MALFORMED_ROOM_RESPONSE"),
        ("ROOM_CREATED bad/id AB12", "INVALID_REQUEST_ID"),
        ("ROOM_CREATED request-1 bad!", "INVALID_ROOM_CODE"),
    ],
)
def test_room_response_parser_rejects_malformed_messages(message, reason):
    with pytest.raises(RoomProtocolError, match=reason):
        parse_room_response(message)


@pytest.mark.parametrize(
    "operation",
    [encode_room_created, encode_room_joined, encode_room_cancelled],
)
def test_room_response_encoders_validate_fields(operation):
    with pytest.raises(RoomProtocolError, match="INVALID_REQUEST_ID"):
        operation("bad/id", "AB12")
    with pytest.raises(RoomProtocolError, match="INVALID_ROOM_CODE"):
        operation("request-1", "bad!")
