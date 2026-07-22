"""SQLite repositories for accounts and completed games."""

import sqlite3
import unicodedata

from server.dal.database import DEFAULT_RATING
from server.dto import GameDTO, UserDTO


class UserRepository:
    """Persist and retrieve user accounts without owning transaction commits."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def create_user(
        self,
        username: str,
        password_hash: bytes,
        salt: bytes,
        rating: int = DEFAULT_RATING,
    ) -> UserDTO:
        """Insert one account and return its database-assigned identity."""
        _require_bytes(password_hash, "INVALID_PASSWORD_HASH")
        _require_bytes(salt, "INVALID_SALT")
        cursor = self._connection.execute(
            """
            INSERT INTO users (username, username_key, password_hash, salt, rating)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, _username_key(username), password_hash, salt, rating),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_username(self, username: str) -> UserDTO | None:
        """Find an account by its normalized, case-insensitive username."""
        row = self._connection.execute(
            """
            SELECT id, username, password_hash, salt, rating, created_at
            FROM users
            WHERE username_key = ?
            """,
            (_username_key(username),),
        ).fetchone()
        return _user_from_row(row) if row is not None else None

    def get_by_id(self, user_id: int) -> UserDTO | None:
        """Find an account by its stable primary key."""
        row = self._connection.execute(
            """
            SELECT id, username, password_hash, salt, rating, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        return _user_from_row(row) if row is not None else None

    def update_rating(self, user_id: int, rating: int) -> UserDTO:
        """Update one rating or raise KeyError when the account does not exist."""
        cursor = self._connection.execute(
            "UPDATE users SET rating = ? WHERE id = ?",
            (rating, user_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(user_id)
        return self.get_by_id(user_id)


class GameRepository:
    """Persist completed game history without owning transaction commits."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def record_game(
        self,
        *,
        white_user_id: int,
        black_user_id: int,
        winner_color: str,
        white_rating_before: int,
        black_rating_before: int,
        white_rating_after: int,
        black_rating_after: int,
        started_at: str,
        ended_at: str,
    ) -> GameDTO:
        """Insert one completed game and return its stored representation."""
        cursor = self._connection.execute(
            """
            INSERT INTO games (
                white_user_id,
                black_user_id,
                winner_color,
                white_rating_before,
                black_rating_before,
                white_rating_after,
                black_rating_after,
                started_at,
                ended_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                white_user_id,
                black_user_id,
                winner_color,
                white_rating_before,
                black_rating_before,
                white_rating_after,
                black_rating_after,
                started_at,
                ended_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, game_id: int) -> GameDTO | None:
        """Find one completed game by its stable primary key."""
        row = self._connection.execute(
            """
            SELECT
                id,
                white_user_id,
                black_user_id,
                winner_color,
                white_rating_before,
                black_rating_before,
                white_rating_after,
                black_rating_after,
                started_at,
                ended_at
            FROM games
            WHERE id = ?
            """,
            (game_id,),
        ).fetchone()
        return _game_from_row(row) if row is not None else None


def _username_key(username: str) -> str:
    if not isinstance(username, str) or not username:
        raise ValueError("INVALID_USERNAME")
    return unicodedata.normalize("NFKC", username).casefold()


def _require_bytes(value: bytes, reason: str) -> None:
    if not isinstance(value, bytes) or not value:
        raise ValueError(reason)


def _user_from_row(row: sqlite3.Row) -> UserDTO:
    return UserDTO(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        salt=row["salt"],
        rating=row["rating"],
        created_at=row["created_at"],
    )


def _game_from_row(row: sqlite3.Row) -> GameDTO:
    return GameDTO(
        id=row["id"],
        white_user_id=row["white_user_id"],
        black_user_id=row["black_user_id"],
        winner_color=row["winner_color"],
        white_rating_before=row["white_rating_before"],
        black_rating_before=row["black_rating_before"],
        white_rating_after=row["white_rating_after"],
        black_rating_after=row["black_rating_after"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )
