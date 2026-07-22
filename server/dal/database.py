"""SQLite connection setup and idempotent schema creation."""

from pathlib import Path
import sqlite3


DEFAULT_RATING = 1200


def connect_database(path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a configured SQLite connection without creating application services."""
    connection = sqlite3.connect(path)
    _configure_connection(connection)
    return connection


def init_schema(connection: sqlite3.Connection) -> None:
    """Create the persistent-account tables when they do not already exist."""
    _configure_connection(connection)
    connection.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            username_key TEXT NOT NULL UNIQUE,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            rating INTEGER NOT NULL DEFAULT {DEFAULT_RATING}
                CHECK (rating >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            white_user_id INTEGER NOT NULL,
            black_user_id INTEGER NOT NULL,
            winner_color TEXT NOT NULL CHECK (winner_color IN ('w', 'b')),
            white_rating_before INTEGER NOT NULL CHECK (white_rating_before >= 0),
            black_rating_before INTEGER NOT NULL CHECK (black_rating_before >= 0),
            white_rating_after INTEGER NOT NULL CHECK (white_rating_after >= 0),
            black_rating_after INTEGER NOT NULL CHECK (black_rating_after >= 0),
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            CHECK (white_user_id <> black_user_id),
            FOREIGN KEY (white_user_id) REFERENCES users(id),
            FOREIGN KEY (black_user_id) REFERENCES users(id)
        );
        """
    )


def _configure_connection(connection: sqlite3.Connection) -> None:
    """Apply settings required by every repository connection."""
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
