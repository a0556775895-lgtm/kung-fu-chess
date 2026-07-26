"""Tests for atomic and idempotent completed-game persistence."""

from types import SimpleNamespace

import pytest

from model.piece import PieceColor
from server.dal.database import connect_database, init_schema
from server.dal.repository import DuplicateGameCompletionError, UserRepository
from server.dal.unit_of_work import SqliteUnitOfWork
from server.game.game_result import FinishReason, GameResult
from server.services.game_completion import GameCompletionService


DURATION_MS = 300_000


@pytest.fixture
def completion_environment():
    connection = connect_database()
    init_schema(connection)
    users = UserRepository(connection)
    white = users.create_user("Alice", b"white-hash", b"white-salt")
    black = users.create_user("Bob", b"black-hash", b"black-salt")
    connection.commit()
    service = GameCompletionService(lambda: SqliteUnitOfWork(connection))
    try:
        yield connection, service, white, black
    finally:
        connection.close()


def _result(
    winner=PieceColor.WHITE,
    reason=FinishReason.KING_CAPTURE,
    duration_ms=DURATION_MS,
):
    return GameResult(winner, reason, duration_ms)


def test_completion_updates_both_ratings_and_records_full_history(
    completion_environment,
):
    connection, service, white, black = completion_environment

    game = service.complete(
        match_instance_id="match-1",
        white_user_id=white.id,
        black_user_id=black.id,
        result=_result(),
    )

    ratings = {
        row["username"]: row["rating"]
        for row in connection.execute("SELECT username, rating FROM users")
    }
    assert ratings == {"Alice": 1216, "Bob": 1184}
    assert game.match_instance_id == "match-1"
    assert game.finish_reason == "KING_CAPTURE"
    assert game.winner_color == "w"
    assert game.white_rating_before == game.black_rating_before == 1200
    assert (game.white_rating_after, game.black_rating_after) == (1216, 1184)
    assert game.duration_ms == DURATION_MS


def test_completion_is_idempotent_and_does_not_apply_elo_twice(
    completion_environment,
):
    connection, service, white, black = completion_environment
    arguments = {
        "match_instance_id": "match-1",
        "white_user_id": white.id,
        "black_user_id": black.id,
        "result": _result(),
    }

    first = service.complete(**arguments)
    second = service.complete(**arguments)

    ratings = [
        row["rating"]
        for row in connection.execute("SELECT rating FROM users ORDER BY id")
    ]
    game_count = connection.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    assert second == first
    assert ratings == [1216, 1184]
    assert game_count == 1


def test_completion_rolls_back_rating_updates_when_game_insert_fails(
    completion_environment,
):
    connection, _, white, black = completion_environment

    def failing_factory():
        unit = SqliteUnitOfWork(connection)

        def fail_record(**_kwargs):
            raise RuntimeError("insert_failed")

        unit.games.record_game = fail_record
        return unit

    service = GameCompletionService(failing_factory)

    with pytest.raises(RuntimeError, match="insert_failed"):
        service.complete(
            match_instance_id="match-1",
            white_user_id=white.id,
            black_user_id=black.id,
            result=_result(),
        )

    ratings = [
        row["rating"]
        for row in connection.execute("SELECT rating FROM users ORDER BY id")
    ]
    assert ratings == [1200, 1200]
    assert connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


def test_completion_rejects_missing_player_and_rolls_back(
    completion_environment,
):
    connection, service, white, _ = completion_environment

    with pytest.raises(KeyError, match="GAME_PLAYER_NOT_FOUND"):
        service.complete(
            match_instance_id="match-1",
            white_user_id=white.id,
            black_user_id=999,
            result=_result(),
        )

    assert connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0


class _FakeUnitOfWork:
    def __init__(self, games, users=None):
        self.games = games
        self.users = users or SimpleNamespace()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_completion_recovers_from_concurrent_unique_conflict():
    persisted = object()
    users = SimpleNamespace(
        get_by_id=lambda user_id: SimpleNamespace(id=user_id, rating=1200),
        update_rating=lambda *_args: None,
    )
    first_games = SimpleNamespace(
        get_by_match_instance_id=lambda _match_id: None,
        record_game=lambda **_kwargs: (_ for _ in ()).throw(
            DuplicateGameCompletionError("race-match")
        ),
    )
    second_games = SimpleNamespace(
        get_by_match_instance_id=lambda _match_id: persisted,
    )
    units = iter((
        _FakeUnitOfWork(first_games, users),
        _FakeUnitOfWork(second_games),
    ))
    service = GameCompletionService(lambda: next(units))

    returned = service.complete(
        match_instance_id="race-match",
        white_user_id=1,
        black_user_id=2,
        result=_result(),
    )

    assert returned is persisted


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"match_instance_id": ""}, "INVALID_MATCH_INSTANCE_ID"),
        ({"white_user_id": True}, "INVALID_PLAYER_ID"),
        ({"black_user_id": 0}, "INVALID_PLAYER_ID"),
        ({"black_user_id": 1}, "PLAYERS_MUST_BE_DIFFERENT"),
        ({"result": None}, "INVALID_GAME_RESULT"),
    ],
)
def test_completion_validates_inputs(changes, reason):
    arguments = {
        "match_instance_id": "match-1",
        "white_user_id": 1,
        "black_user_id": 2,
        "result": _result(),
    }
    arguments.update(changes)
    service = GameCompletionService(lambda: None)

    with pytest.raises(ValueError, match=reason):
        service.complete(**arguments)


def test_completion_service_requires_unit_of_work_factory():
    with pytest.raises(TypeError, match="UNIT_OF_WORK_FACTORY_NOT_CALLABLE"):
        GameCompletionService(None)
