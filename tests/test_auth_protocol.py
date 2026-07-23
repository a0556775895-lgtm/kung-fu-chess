"""Unit tests for persistent account authentication wire messages."""

import pytest

from networking.auth_protocol import (
    AuthProtocolError,
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    encode_auth_ok,
    encode_login,
    encode_register,
    parse_auth_request,
    parse_auth_response,
)


def test_register_round_trip_preserves_unicode_and_whitespace_password():
    request = RegisterRequest("register-1", "דנה-3", "סיסמה ארוכה וחזקה 123")

    assert parse_auth_request(encode_register(request)) == request


def test_login_round_trip_preserves_password_control_characters():
    request = LoginRequest("login-1", "Alice", "long password\nwith\ttabs")

    assert parse_auth_request(encode_login(request)) == request


def test_auth_ok_round_trip_contains_only_public_account_data():
    response = AuthResponse("login-2", 17, "Alice", 1200)

    encoded = encode_auth_ok(response)

    assert parse_auth_response(encoded) == response
    assert "password" not in encoded


@pytest.mark.parametrize(
    "message,reason",
    [
        (None, "MESSAGE_NOT_TEXT"),
        ("", "MALFORMED_AUTH_REQUEST"),
        ("JOIN request-1 {}", "MALFORMED_AUTH_REQUEST"),
        ("LOGIN request-1", "MALFORMED_AUTH_REQUEST"),
        ("LOGIN bad/id {}", "INVALID_REQUEST_ID"),
        ("LOGIN request-1 not-json", "MALFORMED_AUTH_REQUEST"),
        (
            'LOGIN request-1 {"username":"Alice"}',
            "MALFORMED_AUTH_REQUEST",
        ),
        (
            'LOGIN request-1 {"username":"A","password":"long password"}',
            "INVALID_USERNAME",
        ),
        (
            'REGISTER request-1 {"username":"Alice","password":42}',
            "INVALID_PASSWORD_VALUE",
        ),
    ],
)
def test_parse_auth_request_rejects_malformed_values(message, reason):
    with pytest.raises(AuthProtocolError, match=reason):
        parse_auth_request(message)


@pytest.mark.parametrize(
    "message",
    [
        "LOGIN_OK request-1 Alice",
        "AUTH_OK request-1",
        "AUTH_OK request-1 []",
        'AUTH_OK request-1 {"user_id":1,"username":"Alice"}',
        'AUTH_OK request-1 {"user_id":true,"username":"Alice","rating":1200}',
        'AUTH_OK request-1 {"user_id":1,"username":"Alice","rating":-1}',
    ],
)
def test_parse_auth_response_rejects_malformed_values(message):
    with pytest.raises(AuthProtocolError):
        parse_auth_response(message)
