"""Tests for composing the production server with persistent SQLite."""

import asyncio

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.piece import PieceColor
from networking.protocol import JoinRequest
from server.dal.database import connect_database
from server.dal.repository import UserRepository
from server.game.game_result import FinishReason, GameResult
from server.main import create_server
from server.services.game_completion import GameCompletionService
from server.services.matchmaker import MatchmakingPlayer
from server.services.session_registry import ActiveSession


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
    assert isinstance(server._admission._completion_service, GameCompletionService)


def test_production_composition_persists_match_completion(sqlite_path):
    server = create_server(sqlite_path)
    connection = connect_database(sqlite_path)
    try:
        users = UserRepository(connection)
        white = users.create_user("Alice", b"white-hash", b"white-salt")
        black = users.create_user("Bob", b"black-hash", b"black-salt")
        connection.commit()
    finally:
        connection.close()

    match = asyncio.run(_admit_players_and_finish(server, white, black))

    connection = connect_database(sqlite_path)
    try:
        stored_game = connection.execute(
            """
            SELECT match_instance_id, finish_reason
            FROM games
            """
        ).fetchone()
        ratings = [
            row["rating"]
            for row in connection.execute(
                "SELECT rating FROM users ORDER BY id"
            )
        ]
    finally:
        connection.close()
        match.close()

    assert tuple(stored_game) == (
        match.match_instance_id,
        "KING_CAPTURE",
    )
    assert ratings == [1216, 1184]


async def _admit_players_and_finish(server, white, black):
    white_player = MatchmakingPlayer(
        ActiveSession("white-token", white.id, white.username, white.rating),
        JoinRequest("join-white", STANDARD_GAME_CONFIG),
    )
    black_player = MatchmakingPlayer(
        ActiveSession("black-token", black.id, black.username, black.rating),
        JoinRequest("join-black", STANDARD_GAME_CONFIG),
    )
    admissions = server._admission.admit_pair(white_player, black_player)
    white_admission = admissions["white-token"]
    black_admission = admissions["black-token"]
    match = white_admission.match
    result = GameResult(
        winner_color=PieceColor.WHITE,
        reason=FinishReason.KING_CAPTURE,
        duration_ms=match.server_time_ms(),
    )

    assert black_admission.match is match
    assert match.finish(result) is True
    return match
