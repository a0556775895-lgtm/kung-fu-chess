"""Authentication-service tests against an in-memory SQLite database."""

import sqlite3

import pytest

from server.dal.database import DEFAULT_RATING, connect_database, init_schema
from server.dal.unit_of_work import SqliteUnitOfWork
from server.services.auth import (
    MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
    AuthError,
    AuthService,
)


VALID_PASSWORD = "correct horse battery staple"


class _PredictableSaltFactory:
    def __init__(self):
        self._value = 0

    def __call__(self, size):
        self._value += 1
        return bytes([self._value]) * size


@pytest.fixture
def auth_environment():
    connection = connect_database()
    init_schema(connection)
    service = AuthService(
        lambda: SqliteUnitOfWork(connection),
        iterations=2,
        salt_factory=_PredictableSaltFactory(),
    )
    try:
        yield connection, service
    finally:
        connection.close()


def test_register_persists_hash_and_default_rating(auth_environment):
    connection, service = auth_environment

    user = service.register("Alice", VALID_PASSWORD)
    stored = connection.execute(
        "SELECT password_hash, salt, rating FROM users WHERE id = ?",
        (user.id,),
    ).fetchone()

    assert user.username == "Alice"
    assert user.rating == stored["rating"] == DEFAULT_RATING
    assert stored["password_hash"] == user.password_hash
    assert stored["salt"] == user.salt
    assert stored["password_hash"] != VALID_PASSWORD.encode("utf-8")
    assert VALID_PASSWORD not in repr(user)
    assert not connection.in_transaction


def test_login_returns_user_for_correct_password(auth_environment):
    _, service = auth_environment
    registered = service.register("Alice", VALID_PASSWORD)

    authenticated = service.login("alice", VALID_PASSWORD)

    assert authenticated == registered


@pytest.mark.parametrize("username,password", [
    ("Alice", "this password is incorrect"),
    ("MissingUser", VALID_PASSWORD),
    ("!", VALID_PASSWORD),
])
def test_login_uses_one_error_for_all_invalid_credentials(
    auth_environment,
    username,
    password,
):
    _, service = auth_environment
    service.register("Alice", VALID_PASSWORD)

    with pytest.raises(AuthError, match="invalid_credentials") as error:
        service.login(username, password)

    assert error.value.reason == "invalid_credentials"


def test_missing_user_still_performs_password_hash(auth_environment, monkeypatch):
    _, service = auth_environment
    calls = []
    original = service._derive_hash

    def recording_hash(password_bytes, salt):
        calls.append((password_bytes, salt))
        return original(password_bytes, salt)

    monkeypatch.setattr(service, "_derive_hash", recording_hash)

    with pytest.raises(AuthError, match="invalid_credentials"):
        service.login("MissingUser", VALID_PASSWORD)

    assert len(calls) == 1


def test_register_rejects_case_variant_duplicate(auth_environment):
    connection, service = auth_environment
    original = service.register("Alice", VALID_PASSWORD)

    with pytest.raises(AuthError, match="username_taken") as error:
        service.register("alice", "another secure password")

    assert error.value.reason == "username_taken"
    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert service.login("ALICE", VALID_PASSWORD) == original


def test_same_password_receives_unique_salt_and_hash(auth_environment):
    _, service = auth_environment

    first = service.register("Alice", VALID_PASSWORD)
    second = service.register("Bob", VALID_PASSWORD)

    assert first.salt != second.salt
    assert first.password_hash != second.password_hash


def test_unicode_and_whitespace_password_round_trip(auth_environment):
    _, service = auth_environment
    password = "סיסמה ארוכה ובטוחה מאוד 🔐"

    registered = service.register("Dana", password)

    assert service.login("Dana", password) == registered


@pytest.mark.parametrize("password", [
    "x" * (MIN_PASSWORD_LENGTH - 1),
    "🔐" * ((MAX_PASSWORD_BYTES // len("🔐".encode("utf-8"))) + 1),
    None,
])
def test_register_enforces_password_length_policy(auth_environment, password):
    connection, service = auth_environment

    with pytest.raises(AuthError, match="invalid_password"):
        service.register("Alice", password)

    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_register_rejects_invalid_username(auth_environment):
    connection, service = auth_environment

    with pytest.raises(AuthError, match="invalid_username"):
        service.register("Alice Smith", VALID_PASSWORD)

    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_unit_of_work_rolls_back_partial_operation(auth_environment):
    connection, _ = auth_environment

    with pytest.raises(RuntimeError, match="later_operation_failed"):
        with SqliteUnitOfWork(connection) as unit_of_work:
            unit_of_work.users.create_user(
                "Alice",
                password_hash=b"derived-hash",
                salt=b"sixteen-byte-key",
            )
            raise RuntimeError("later_operation_failed")

    assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert not connection.in_transaction


def test_owned_unit_of_work_closes_its_connection():
    connection = connect_database()
    init_schema(connection)

    with SqliteUnitOfWork(connection, close_connection=True):
        pass

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
