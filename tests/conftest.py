"""Shared test composition for authenticated WebSocket servers."""

from pathlib import Path
import uuid

import pytest

from server.dal.database import connect_database, init_schema
from server.dal.unit_of_work import SqliteUnitOfWork
from server.services.auth import AuthService


@pytest.fixture
def sqlite_path():
    """Provide one ignored SQLite path and remove every sidecar after the test."""
    database_path = Path.cwd() / f"kfc_test_{uuid.uuid4().hex}.db"
    try:
        yield database_path
    finally:
        for suffix in ("", "-journal", "-shm", "-wal"):
            candidate = Path(f"{database_path}{suffix}")
            if candidate.exists():
                candidate.unlink()


@pytest.fixture
def auth_service(sqlite_path):
    """Return a fast AuthService backed by an isolated SQLite file."""
    schema_connection = connect_database(sqlite_path)
    try:
        init_schema(schema_connection)
        schema_connection.commit()
    finally:
        schema_connection.close()

    def unit_of_work_factory():
        return SqliteUnitOfWork(
            connect_database(sqlite_path),
            close_connection=True,
        )

    yield AuthService(unit_of_work_factory, iterations=1)
