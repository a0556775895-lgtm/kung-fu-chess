"""Unit tests for bounded rating-bucket matchmaking."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocol import JoinRequest
from server.services.matchmaker import (
    AlreadyQueuedError,
    Matchmaker,
    MatchmakingPlayer,
    MatchmakingTimeoutError,
)
from server.services.session_registry import ActiveSession


def _player(token, rating):
    user_id = sum(ord(character) for character in token)
    session = ActiveSession(token, user_id, token, rating)
    return MatchmakingPlayer(
        session,
        JoinRequest(f"join-{token}", STANDARD_GAME_CONFIG),
    )


def _result_factory(record):
    def create_pair(first, second):
        record.append((first.session.token, second.session.token))
        return {
            first.session.token: f"matched-{first.session.token}",
            second.session.token: f"matched-{second.session.token}",
        }

    return create_pair


async def _queue(matchmaker, player):
    task = asyncio.create_task(matchmaker.find_or_wait(player))
    await asyncio.sleep(0)
    return task


def test_matchmaker_chooses_closest_rating_without_scanning_players():
    async def scenario():
        pairs = []
        matchmaker = Matchmaker(
            _result_factory(pairs),
            rating_range=100,
            timeout_seconds=1,
        )
        far = await _queue(matchmaker, _player("far", 1100))
        close = await _queue(matchmaker, _player("close", 1201))

        incoming_result = await matchmaker.find_or_wait(_player("new", 1200))

        assert incoming_result == "matched-new"
        assert await close == "matched-close"
        assert pairs == [("close", "new")]
        assert matchmaker.waiting_count == 1
        far.cancel()
        with pytest.raises(asyncio.CancelledError):
            await far
        assert matchmaker.waiting_count == 0

    asyncio.run(scenario())


def test_matchmaker_prefers_oldest_player_when_distance_is_equal():
    async def scenario():
        pairs = []
        matchmaker = Matchmaker(
            _result_factory(pairs),
            rating_range=100,
            timeout_seconds=1,
        )
        older = await _queue(matchmaker, _player("older", 1100))
        newer = await _queue(matchmaker, _player("newer", 1300))

        assert await matchmaker.find_or_wait(_player("new", 1200)) == "matched-new"
        assert await older == "matched-older"
        assert pairs == [("older", "new")]
        newer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await newer

    asyncio.run(scenario())


def test_matchmaker_times_out_and_removes_empty_bucket():
    async def scenario():
        matchmaker = Matchmaker(
            lambda *_players: None,
            rating_range=100,
            timeout_seconds=0.001,
        )

        with pytest.raises(MatchmakingTimeoutError):
            await matchmaker.find_or_wait(_player("alone", 1200))

        assert matchmaker.waiting_count == 0
        assert matchmaker.bucket_count == 0

    asyncio.run(scenario())


def test_matchmaker_returns_completed_pair_at_timeout_boundary(monkeypatch):
    async def scenario():
        pairs = []
        matchmaker = Matchmaker(
            _result_factory(pairs),
            rating_range=100,
            timeout_seconds=1,
        )

        async def complete_pair_then_timeout(_awaitable, timeout):
            assert timeout == 1.0
            assert (
                await matchmaker.find_or_wait(_player("second", 1200))
                == "matched-second"
            )
            raise TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", complete_pair_then_timeout)

        assert (
            await matchmaker.find_or_wait(_player("first", 1200))
            == "matched-first"
        )
        assert pairs == [("first", "second")]
        assert matchmaker.waiting_count == 0

    asyncio.run(scenario())


def test_matchmaker_rejects_same_session_queued_twice():
    async def scenario():
        matchmaker = Matchmaker(
            lambda *_players: None,
            rating_range=100,
            timeout_seconds=1,
        )
        player = _player("same", 1200)
        waiting = await _queue(matchmaker, player)

        with pytest.raises(AlreadyQueuedError):
            await matchmaker.find_or_wait(player)

        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting

    asyncio.run(scenario())


def test_matchmaker_propagates_pair_creation_failure_to_both_players():
    async def scenario():
        def fail_pairing(_first, _second):
            raise RuntimeError("pair_failed")

        matchmaker = Matchmaker(
            fail_pairing,
            rating_range=100,
            timeout_seconds=1,
        )
        first = await _queue(matchmaker, _player("first", 1200))

        with pytest.raises(RuntimeError, match="pair_failed"):
            await matchmaker.find_or_wait(_player("second", 1200))
        with pytest.raises(RuntimeError, match="pair_failed"):
            await first

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "arguments,reason,error_type",
    [
        ((None,), "PAIR_FACTORY_NOT_CALLABLE", TypeError),
        ((lambda: None,), "INVALID_RATING_RANGE", ValueError),
        ((lambda: None,), "INVALID_MATCH_TIMEOUT", ValueError),
    ],
)
def test_matchmaker_validates_constructor(arguments, reason, error_type):
    kwargs = {
        "rating_range": 100,
        "timeout_seconds": 1,
    }
    if reason == "INVALID_RATING_RANGE":
        kwargs["rating_range"] = -1
    if reason == "INVALID_MATCH_TIMEOUT":
        kwargs["timeout_seconds"] = 0

    with pytest.raises(error_type, match=reason):
        Matchmaker(*arguments, **kwargs)
