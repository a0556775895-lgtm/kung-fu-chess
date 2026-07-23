"""Text envelopes and JSON payloads for persistent account authentication."""
"""מגדיר כיצד הודעות אימות עוברות ברשת, ומספק פונקציות קידוד ופענוח"""
from dataclasses import dataclass, field
import json
import re
from typing import TypeAlias


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
MIN_USERNAME_LENGTH = 2
MAX_USERNAME_LENGTH = 20


class AuthProtocolError(ValueError):
    """A malformed authentication message or invalid field value."""


@dataclass(frozen=True, slots=True)
class RegisterRequest:
    """Create one persistent account before joining a game."""

    request_id: str
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class LoginRequest:
    """Authenticate one existing account before joining a game."""

    request_id: str
    username: str
    password: str = field(repr=False)


AuthRequest: TypeAlias = RegisterRequest | LoginRequest


@dataclass(frozen=True, slots=True)
class AuthResponse:
    """Public account identity returned after successful authentication."""

    request_id: str
    user_id: int
    username: str
    rating: int


def encode_register(request: RegisterRequest) -> str:
    """Encode a registration request without exposing its password in repr."""
    """מקבלת RegisterRequest וממירה אותו למחרוזת רשת"""
    return _encode_request("REGISTER", request)


def encode_login(request: LoginRequest) -> str:
    """Encode a login request as a text envelope containing a JSON payload."""
    """מקבלת את בקשת הלוגין וממירה אותה למחרוזת רשת, כמו ההרשמה"""
    return _encode_request("LOGIN", request)


def parse_auth_request(message: str) -> AuthRequest:
    """Parse one REGISTER or LOGIN request and validate its wire-level fields."""
    """מפענחת את ההודעה שהגיעה לשרת"""
    if not isinstance(message, str):
        raise AuthProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split(maxsplit=2)
    if len(parts) != 3 or parts[0] not in {"REGISTER", "LOGIN"}:
        raise AuthProtocolError("MALFORMED_AUTH_REQUEST")

    operation, request_id, payload_text = parts
    _validate_request_id(request_id)
    payload = _decode_object(payload_text, "MALFORMED_AUTH_REQUEST")
    if set(payload) != {"username", "password"}:
        raise AuthProtocolError("MALFORMED_AUTH_REQUEST")

    username = payload["username"]
    password = payload["password"]
    validate_username(username)
    if not isinstance(password, str):
        raise AuthProtocolError("INVALID_PASSWORD_VALUE")

    request_type = RegisterRequest if operation == "REGISTER" else LoginRequest
    return request_type(request_id, username, password)


def encode_auth_ok(response: AuthResponse) -> str:
    """Encode public account data after successful registration or login."""
    _validate_response(response)
    payload = {
        "rating": response.rating,
        "user_id": response.user_id,
        "username": response.username,
    }
    return f"AUTH_OK {response.request_id} {_encode_object(payload)}"


def parse_auth_response(message: str) -> AuthResponse:
    """Parse and validate an AUTH_OK response."""
    if not isinstance(message, str):
        raise AuthProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split(maxsplit=2)
    if len(parts) != 3 or parts[0] != "AUTH_OK":
        raise AuthProtocolError("MALFORMED_AUTH_RESPONSE")

    _, request_id, payload_text = parts
    _validate_request_id(request_id)
    payload = _decode_object(payload_text, "MALFORMED_AUTH_RESPONSE")
    if set(payload) != {"user_id", "username", "rating"}:
        raise AuthProtocolError("MALFORMED_AUTH_RESPONSE")

    response = AuthResponse(
        request_id=request_id,
        user_id=payload["user_id"],
        username=payload["username"],
        rating=payload["rating"],
    )
    _validate_response(response)
    return response


def validate_username(username: str) -> None:
    """Require a short whitespace-free Unicode name with safe separators."""
    if not isinstance(username, str):
        raise AuthProtocolError("INVALID_USERNAME")
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise AuthProtocolError("INVALID_USERNAME")
    if not all(character.isalnum() or character in "_-" for character in username):
        raise AuthProtocolError("INVALID_USERNAME")
    if not any(character.isalnum() for character in username):
        raise AuthProtocolError("INVALID_USERNAME")


def _encode_request(operation: str, request: AuthRequest) -> str:
    _validate_request_id(request.request_id)
    validate_username(request.username)
    if not isinstance(request.password, str):
        raise AuthProtocolError("INVALID_PASSWORD_VALUE")
    payload = {"password": request.password, "username": request.username}
    return f"{operation} {request.request_id} {_encode_object(payload)}"


def _validate_response(response: AuthResponse) -> None:
    _validate_request_id(response.request_id)
    validate_username(response.username)
    if (
        isinstance(response.user_id, bool)
        or not isinstance(response.user_id, int)
        or response.user_id <= 0
    ):
        raise AuthProtocolError("INVALID_USER_ID")
    if (
        isinstance(response.rating, bool)
        or not isinstance(response.rating, int)
        or response.rating < 0
    ):
        raise AuthProtocolError("INVALID_RATING")


def _validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise AuthProtocolError("INVALID_REQUEST_ID")


def _encode_object(payload: dict) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _decode_object(payload_text: str, reason: str) -> dict:
    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError) as exc:
        raise AuthProtocolError(reason) from exc
    if not isinstance(payload, dict):
        raise AuthProtocolError(reason)
    return payload
