"""Unit tests for the standalone username login wire protocol."""

import pytest

from networking.login_protocol import (
    LoginProtocolError,
    LoginRequest,
    encode_login,
    encode_login_ok,
    parse_login,
    parse_login_response,
    validate_username,
)


@pytest.mark.parametrize("username", ["Alice", "player_2", "דנה-3"])
def test_login_request_round_trip_supports_valid_unicode_names(username):
    request = LoginRequest("login-1", username)

    assert parse_login(encode_login(request)) == request


def test_login_ok_round_trip_preserves_request_and_display_name():
    response = parse_login_response(encode_login_ok("login-2", "Alice"))

    assert response.request_id == "login-2"
    assert response.username == "Alice"


@pytest.mark.parametrize(
    "message,reason",
    [
        (None, "MESSAGE_NOT_TEXT"),
        ("", "MALFORMED_LOGIN"),
        ("JOIN login-1 Alice", "MALFORMED_LOGIN"),
        ("LOGIN login-1", "MALFORMED_LOGIN"),
        ("LOGIN login-1 Alice Smith", "MALFORMED_LOGIN"),
        ("LOGIN bad/id Alice", "INVALID_REQUEST_ID"),
        ("LOGIN login-1 A", "INVALID_USERNAME"),
        ("LOGIN login-1 Alice!", "INVALID_USERNAME"),
    ],
)
def test_parse_login_rejects_malformed_messages(message, reason):
    with pytest.raises(LoginProtocolError, match=reason):
        parse_login(message)


@pytest.mark.parametrize(
    "username",
    ["A", "a" * 21, "--", "Alice Smith", "Alice!"],
)
def test_username_validation_rejects_invalid_values(username):
    with pytest.raises(LoginProtocolError, match="INVALID_USERNAME"):
        validate_username(username)


@pytest.mark.parametrize(
    "message",
    ["OK login-1 Alice", "LOGIN_OK login-1", "LOGIN_OK bad/id Alice"],
)
def test_login_response_rejects_malformed_values(message):
    with pytest.raises(LoginProtocolError):
        parse_login_response(message)
