"""Independent text protocol for username-only login messages."""

from dataclasses import dataclass
import re


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
MIN_USERNAME_LENGTH = 2
MAX_USERNAME_LENGTH = 20


class LoginProtocolError(ValueError):
    """A malformed LOGIN message or invalid username value."""


@dataclass(frozen=True)
class LoginRequest:
    """A temporary username identity requested before joining a game."""

    request_id: str
    username: str


@dataclass(frozen=True)
class LoginResponse:
    """Confirmation of the username claimed for the current connection."""

    request_id: str
    username: str


def encode_login(request: LoginRequest) -> str:
    """Encode a username-only login request as one text message."""
    _validate_request_id(request.request_id)
    validate_username(request.username)
    return f"LOGIN {request.request_id} {request.username}"


def parse_login(message: str) -> LoginRequest:
    """Parse LOGIN and validate its request id and username."""
    if not isinstance(message, str):
        raise LoginProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 3 or parts[0] != "LOGIN":
        raise LoginProtocolError("MALFORMED_LOGIN")
    _validate_request_id(parts[1])
    validate_username(parts[2])
    return LoginRequest(parts[1], parts[2])


def encode_login_ok(request_id: str, username: str) -> str:
    """Confirm the temporary username claimed by a connection."""
    _validate_request_id(request_id)
    validate_username(username)
    return f"LOGIN_OK {request_id} {username}"


def parse_login_response(message: str) -> LoginResponse:
    """Parse a successful LOGIN_OK response."""
    if not isinstance(message, str):
        raise LoginProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 3 or parts[0] != "LOGIN_OK":
        raise LoginProtocolError("MALFORMED_LOGIN_RESPONSE")
    _validate_request_id(parts[1])
    validate_username(parts[2])
    return LoginResponse(parts[1], parts[2])


def validate_username(username: str) -> None:
    """Require a short whitespace-free Unicode name with two safe separators."""
    if not isinstance(username, str):
        raise LoginProtocolError("INVALID_USERNAME")
    if not MIN_USERNAME_LENGTH <= len(username) <= MAX_USERNAME_LENGTH:
        raise LoginProtocolError("INVALID_USERNAME")
    if not all(character.isalnum() or character in "_-" for character in username):
        raise LoginProtocolError("INVALID_USERNAME")
    if not any(character.isalnum() for character in username):
        raise LoginProtocolError("INVALID_USERNAME")


def _validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise LoginProtocolError("INVALID_REQUEST_ID")
