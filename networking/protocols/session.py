"""Text protocol messages for restoring a session after disconnection."""

from dataclasses import dataclass, field
import re


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SESSION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


class SessionProtocolError(ValueError):
    """A malformed reconnect request or response."""


@dataclass(frozen=True, slots=True)
class ReconnectRequest:
    """Ask the server to attach a new socket to one existing session."""

    request_id: str
    session_token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReconnectResponse:
    """Confirmation correlated with the reconnect request."""

    request_id: str


def encode_reconnect(request: ReconnectRequest) -> str:
    """Encode a reconnect request without exposing the token in JSON."""
    if not isinstance(request, ReconnectRequest):
        raise SessionProtocolError("INVALID_RECONNECT_REQUEST")
    _validate_request_id(request.request_id)
    _validate_session_token(request.session_token)
    return f"RECONNECT {request.request_id} {request.session_token}"


def parse_reconnect(message: str) -> ReconnectRequest:
    """Parse and validate one reconnect request from a new socket."""
    if not isinstance(message, str):
        raise SessionProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 3 or parts[0] != "RECONNECT":
        raise SessionProtocolError("MALFORMED_RECONNECT")

    request_id, session_token = parts[1:]
    _validate_request_id(request_id)
    _validate_session_token(session_token)
    return ReconnectRequest(request_id, session_token)


def encode_reconnect_ok(response: ReconnectResponse) -> str:
    """Confirm that the new socket was restored to the existing session."""
    if not isinstance(response, ReconnectResponse):
        raise SessionProtocolError("INVALID_RECONNECT_RESPONSE")
    _validate_request_id(response.request_id)
    return f"RECONNECT_OK {response.request_id}"


def parse_reconnect_response(message: str) -> ReconnectResponse:
    """Parse a successful reconnect confirmation."""
    if not isinstance(message, str):
        raise SessionProtocolError("MESSAGE_NOT_TEXT")
    parts = message.strip().split()
    if len(parts) != 2 or parts[0] != "RECONNECT_OK":
        raise SessionProtocolError("MALFORMED_RECONNECT_RESPONSE")
    _validate_request_id(parts[1])
    return ReconnectResponse(parts[1])


def _validate_request_id(request_id: str) -> None:
    if (
        not isinstance(request_id, str)
        or _REQUEST_ID_RE.fullmatch(request_id) is None
    ):
        raise SessionProtocolError("INVALID_REQUEST_ID")


def _validate_session_token(session_token: str) -> None:
    if (
        not isinstance(session_token, str)
        or _SESSION_TOKEN_RE.fullmatch(session_token) is None
    ):
        raise SessionProtocolError("INVALID_SESSION_TOKEN")
