"""Unit tests for the reconnect session protocol."""

import pytest

from networking.protocols.session import (
    ReconnectRequest,
    ReconnectResponse,
    SessionProtocolError,
    encode_reconnect,
    encode_reconnect_ok,
    parse_reconnect,
    parse_reconnect_response,
)
from server import config


def test_reconnect_request_round_trip_hides_token_from_repr():
    request = ReconnectRequest("reconnect-1", "secret_session-token")

    message = encode_reconnect(request)

    assert message == "RECONNECT reconnect-1 secret_session-token"
    assert parse_reconnect(message) == request
    assert "secret_session-token" not in repr(request)


def test_reconnect_response_round_trip():
    response = ReconnectResponse("reconnect-1")

    assert parse_reconnect_response(
        encode_reconnect_ok(response)
    ) == response


def test_reconnect_grace_period_is_owned_by_server_config():
    assert config.RECONNECT_GRACE_PERIOD_SECONDS == 20.0


@pytest.mark.parametrize(
    "message,reason",
    [
        (b"RECONNECT reconnect-1 token", "MESSAGE_NOT_TEXT"),
        ("LOGIN reconnect-1 token", "MALFORMED_RECONNECT"),
        ("RECONNECT reconnect-1", "MALFORMED_RECONNECT"),
        ("RECONNECT reconnect-1 token extra", "MALFORMED_RECONNECT"),
        ("RECONNECT invalid/request token", "INVALID_REQUEST_ID"),
        ("RECONNECT reconnect-1 invalid+token", "INVALID_SESSION_TOKEN"),
    ],
)
def test_parse_reconnect_rejects_invalid_messages(message, reason):
    with pytest.raises(SessionProtocolError, match=reason):
        parse_reconnect(message)


@pytest.mark.parametrize(
    "value,reason",
    [
        (object(), "INVALID_RECONNECT_REQUEST"),
        (ReconnectRequest("invalid/request", "token"), "INVALID_REQUEST_ID"),
        (ReconnectRequest("reconnect-1", ""), "INVALID_SESSION_TOKEN"),
    ],
)
def test_encode_reconnect_rejects_invalid_request(value, reason):
    with pytest.raises(SessionProtocolError, match=reason):
        encode_reconnect(value)


@pytest.mark.parametrize(
    "message,reason",
    [
        (b"RECONNECT_OK reconnect-1", "MESSAGE_NOT_TEXT"),
        ("OK reconnect-1", "MALFORMED_RECONNECT_RESPONSE"),
        ("RECONNECT_OK", "MALFORMED_RECONNECT_RESPONSE"),
        ("RECONNECT_OK invalid/request", "INVALID_REQUEST_ID"),
    ],
)
def test_parse_reconnect_response_rejects_invalid_messages(message, reason):
    with pytest.raises(SessionProtocolError, match=reason):
        parse_reconnect_response(message)


@pytest.mark.parametrize(
    "response,reason",
    [
        (object(), "INVALID_RECONNECT_RESPONSE"),
        (ReconnectResponse("invalid/request"), "INVALID_REQUEST_ID"),
    ],
)
def test_encode_reconnect_ok_rejects_invalid_response(response, reason):
    with pytest.raises(SessionProtocolError, match=reason):
        encode_reconnect_ok(response)
