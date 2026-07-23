"""Explicit SQLite transaction boundary for server application services."""
"""החיבור בין הDB לשאר השרת"""
import sqlite3

from server.dal.repository import GameRepository, UserRepository


class SqliteUnitOfWork:
    """Commit a service operation on success and roll it back on failure."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        close_connection: bool = False,
    ):
        self._connection = connection
        self._close_connection = close_connection
        self.users = UserRepository(connection)
        self.games = GameRepository(connection)
        self._entered = False
        self._closed = False

    def __enter__(self):
        if self._closed:
            raise RuntimeError("UNIT_OF_WORK_CLOSED")
        if self._entered:
            raise RuntimeError("UNIT_OF_WORK_ALREADY_ACTIVE")
        self._entered = True
        return self

    def __exit__(self, exception_type, exception, traceback) -> bool:
        try:
            if exception_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._entered = False
            if self._close_connection:
                self._connection.close()
                self._closed = True
        return False
