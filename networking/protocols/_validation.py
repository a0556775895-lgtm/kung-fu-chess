"""Shared structural validation for identifiers carried by wire protocols."""

import re


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_SESSION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def is_valid_request_id(value) -> bool:
    """Return whether a value is a safe request correlation identifier."""
    return (
        isinstance(value, str)
        and _REQUEST_ID_RE.fullmatch(value) is not None
    )


def is_valid_session_token(value) -> bool:
    """Return whether a value has the format produced by the token factory."""
    return (
        isinstance(value, str)
        and _SESSION_TOKEN_RE.fullmatch(value) is not None
    )
