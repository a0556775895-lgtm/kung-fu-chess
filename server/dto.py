"""Plain data-transfer objects returned by the server persistence layer."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UserDTO:
    """One persisted account, including credentials required by AuthService."""

    id: int
    username: str
    password_hash: bytes = field(repr=False)
    salt: bytes = field(repr=False)
    rating: int
    created_at: str


@dataclass(frozen=True, slots=True)
class GameDTO:
    """One immutable record of a completed rated game."""

    id: int
    white_user_id: int
    black_user_id: int
    winner_color: str
    white_rating_before: int
    black_rating_before: int
    white_rating_after: int
    black_rating_after: int
    started_at: str
    ended_at: str
