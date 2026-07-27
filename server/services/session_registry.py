"""In-memory ownership of authenticated sessions currently connected."""
"""אוביקט שמיצג משתמש מאומת פעיל"""
from dataclasses import dataclass, field
import secrets
import unicodedata

from model.piece import PieceColor


@dataclass(slots=True)
class ActiveSession:
    """Temporary authenticated identity used later for matchmaking and reconnect."""

    token: str = field(repr=False)
    user_id: int
    username: str
    rating: int
    game_id: str | None = None
    color: PieceColor | None = None
    is_connected: bool = True


class SessionRegistry:
    """Own active sessions and prevent duplicate connections for one account."""

    def __init__(self, token_factory=None):
        """Start empty and accept an injectable secure token factory."""
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        if not callable(self._token_factory):
            raise TypeError("TOKEN_FACTORY_NOT_CALLABLE")
        self._by_token = {}
        self._token_by_username = {}

    def create(self, user_id: int, username: str, rating: int) -> ActiveSession | None:
        """Create a session, or return None when the username is already active."""
        _validate_user_id(user_id)
        _validate_rating(rating)
        key = _identity_key(username)
        if key in self._token_by_username:
            return None

        token = self._token_factory()
        _validate_token(token)
        if token in self._by_token:
            raise RuntimeError("SESSION_TOKEN_COLLISION")

        session = ActiveSession(token, user_id, username, rating)
        self._by_token[token] = session
        self._token_by_username[key] = token
        return session

    def get(self, token: str) -> ActiveSession | None:
        """Find an active session by its reconnect token."""
        _validate_token(token)
        return self._by_token.get(token)

    def mark_disconnected(self, token: str) -> ActiveSession | None:
        """Retain one session and its reserved identity without a live socket."""
        _validate_token(token)
        session = self._by_token.get(token)
        if session is not None:
            session.is_connected = False
        return session

    def mark_connected(self, token: str) -> ActiveSession | None:
        """Mark one retained session as owning a live socket again."""
        _validate_token(token)
        session = self._by_token.get(token)
        if session is not None:
            session.is_connected = True
        return session

    def release(self, token: str) -> bool:
        """Remove one session by token, returning whether it was active."""
        _validate_token(token)
        session = self._by_token.pop(token, None)
        if session is None:
            return False
        self._token_by_username.pop(_identity_key(session.username), None)
        return True

    def clear(self) -> int:
        """Release every session during an explicit server shutdown."""
        count = len(self._by_token)
        self._by_token.clear()
        self._token_by_username.clear()
        return count

    def is_active(self, username: str) -> bool:
        """Return whether an equivalent username is currently reserved."""
        return _identity_key(username) in self._token_by_username

    def active_usernames(self) -> tuple[str, ...]:
        """Return the preserved display spelling of every active username."""
        return tuple(
            self._by_token[token].username
            for token in self._token_by_username.values()
        )

    def __len__(self) -> int:
        """Return the number of active sessions."""
        return len(self._by_token)


def _identity_key(username: str) -> str:
    if not isinstance(username, str) or not username:
        raise ValueError("INVALID_USERNAME")
    return unicodedata.normalize("NFKC", username).casefold()


def _validate_token(token: str) -> None:
    if not isinstance(token, str) or not token or len(token) > 256:
        raise ValueError("INVALID_SESSION_TOKEN")


def _validate_user_id(user_id: int) -> None:
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("INVALID_USER_ID")


def _validate_rating(rating: int) -> None:
    if isinstance(rating, bool) or not isinstance(rating, int) or rating < 0:
        raise ValueError("INVALID_RATING")
