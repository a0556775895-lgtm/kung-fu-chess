"""Tests for composing the production server with persistent SQLite."""

from server.dal.database import connect_database
from server.main import create_server


def test_create_server_initializes_persistent_database(sqlite_path):
    server = create_server(sqlite_path)

    connection = connect_database(sqlite_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()

    assert not server.is_running
    assert {"users", "games"} <= tables
