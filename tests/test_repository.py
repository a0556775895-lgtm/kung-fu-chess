"""In-memory tests for the stage-D SQLite persistence boundary."""

import sqlite3

import pytest

from server.dal.database import DEFAULT_RATING, connect_database, init_schema
from server.dal.repository import GameRepository, UserRepository


@pytest.fixture
def connection():
    database = connect_database()
    init_schema(database)
    try:
        yield database
    finally:
        database.close()


def _create_user(repository, username):
    return repository.create_user(
        username=username,
        password_hash=f"hash-{username}".encode(),
        salt=f"salt-{username}".encode(),
    )


def test_init_schema_is_idempotent_and_enables_foreign_keys():
    connection = connect_database()
    try:
        init_schema(connection)
        init_schema(connection)

        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]

        assert {"users", "games"}.issubset(tables)
        assert foreign_keys_enabled == 1
    finally:
        connection.close()


def test_user_repository_creates_and_finds_normalized_username(connection):
    repository = UserRepository(connection)

    created = _create_user(repository, "Café")
    loaded = repository.get_by_username("Cafe\u0301")

    assert loaded == created
    assert created.username == "Café"
    assert created.rating == DEFAULT_RATING
    assert created.created_at
    assert "hash-Café" not in repr(created)


def test_user_repository_rejects_case_variant_duplicate(connection):
    repository = UserRepository(connection)
    _create_user(repository, "Alice")

    with pytest.raises(sqlite3.IntegrityError):
        _create_user(repository, "alice")


def test_user_repository_updates_rating_and_rejects_missing_user(connection):
    repository = UserRepository(connection)
    user = _create_user(repository, "Alice")

    updated = repository.update_rating(user.id, 1232)

    assert updated.rating == 1232
    assert repository.get_by_id(user.id) == updated
    with pytest.raises(KeyError):
        repository.update_rating(999, 1200)


def test_game_repository_records_complete_rating_history(connection):
    users = UserRepository(connection)
    games = GameRepository(connection)
    white = _create_user(users, "Alice")
    black = _create_user(users, "Bob")

    game = games.record_game(
        white_user_id=white.id,
        black_user_id=black.id,
        winner_color="w",
        white_rating_before=1200,
        black_rating_before=1200,
        white_rating_after=1216,
        black_rating_after=1184,
        started_at="2026-07-22T12:00:00Z",
        ended_at="2026-07-22T12:05:00Z",
    )

    assert games.get_by_id(game.id) == game
    assert game.white_user_id == white.id
    assert game.black_user_id == black.id
    assert game.winner_color == "w"
    assert (game.white_rating_after, game.black_rating_after) == (1216, 1184)


def test_game_repository_enforces_user_foreign_keys(connection):
    games = GameRepository(connection)

    with pytest.raises(sqlite3.IntegrityError):
        games.record_game(
            white_user_id=1,
            black_user_id=2,
            winner_color="w",
            white_rating_before=1200,
            black_rating_before=1200,
            white_rating_after=1216,
            black_rating_after=1184,
            started_at="2026-07-22T12:00:00Z",
            ended_at="2026-07-22T12:05:00Z",
        )


def test_repositories_leave_transaction_control_to_caller(connection):
    users = UserRepository(connection)
    _create_user(users, "Alice")

    connection.rollback()

    assert users.get_by_username("Alice") is None
