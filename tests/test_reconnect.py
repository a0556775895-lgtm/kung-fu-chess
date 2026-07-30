"""Unit tests for atomic server-side session restoration."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG, create_board
from engine.game_engine import GameEngine
from model.game_config import GameConfig
from model.piece import PieceColor
from networking.protocols.game import (
    JoinRequest,
    decode_event,
    decode_state,
    parse_config_response,
)
from server.game.admission import GameAdmission
from server.game.game_registry import GameRegistry
from server.game.game_result import FinishReason, GameResult
from server.game.match import Match
from server.services.reconnect import ReconnectError, ReconnectService
from server.services.session_registry import SessionRegistry, SessionState
from server.transport.connection import ConnectionContext, ConnectionRole


def _setup_active_player():
    sessions = SessionRegistry(token_factory=lambda: "session-token")
    session = sessions.create(1, "Alice", 1200)
    session.game_id = "game-1"
    session.color = PieceColor.WHITE

    registry = GameRegistry()
    match = Match(
        "game-1",
        GameEngine(create_board(STANDARD_GAME_CONFIG)),
        game_config=STANDARD_GAME_CONFIG,
    )
    registry.add(match)
    original = ConnectionContext(
        "original",
        "game-1",
        ConnectionRole.PLAYER,
        PieceColor.WHITE,
        user_id=1,
        username="Alice",
        session_token="session-token",
        websocket=object(),
    )
    match.add_connection(original)
    admission = GameAdmission(registry)
    service = ReconnectService(sessions, registry, admission)
    return sessions, session, registry, match, original, service


def _drain(context):
    return [
        context.outbound.get_nowait()
        for _ in range(context.outbound.qsize())
    ]


def test_disconnect_and_restore_preserve_match_color_and_snapshot():
    async def scenario():
        sessions, session, _, match, original, service = (
            _setup_active_player()
        )
        assert await service.disconnect(session, original)
        assert not session.is_connected
        assert match.connections() == ()

        requested = GameConfig(1, 10, 10, "future")
        request = JoinRequest(
            "join-reconnect",
            "session-token",
            requested,
        )
        restored_session, result = await service.restore(request, object())

        assert restored_session is session
        assert session.is_connected
        assert sessions.get("session-token") is session
        assert result.match is match
        assert result.context.connection_id != "original"
        assert result.context.game_id == "game-1"
        assert result.context.color is PieceColor.WHITE
        assert result.context.user_id == 1
        assert result.context.username == "Alice"
        assert result.context.session_token == "session-token"

        config_message, state_message, reconnect_message = _drain(result.context)
        config = parse_config_response(config_message)
        state = decode_state(state_message)
        reconnect_event = decode_event(reconnect_message)
        assert config.was_overridden
        assert config.effective_config == STANDARD_GAME_CONFIG
        assert state.game_id == "game-1"
        assert state.assigned_color == "w"
        assert state.player_names["w"] == "Alice"
        assert reconnect_event["type"] == "PLAYER_RECONNECTED"
        assert reconnect_event["color"] == "w"
        assert not match.is_paused

    asyncio.run(scenario())


def test_disconnect_releases_session_when_match_is_missing_or_finished():
    async def scenario():
        sessions, session, registry, match, context, service = (
            _setup_active_player()
        )
        registry.remove("game-1")
        assert not await service.disconnect(session, context)
        assert sessions.get("session-token") is None

        sessions, session, _, match, context, service = _setup_active_player()
        match.finish(
            GameResult(
                PieceColor.BLACK,
                FinishReason.RESIGN,
                100,
            )
        )
        assert not await service.disconnect(session, context)
        assert sessions.get("session-token") is None

    asyncio.run(scenario())


def test_restore_rejects_invalid_connected_and_unavailable_sessions():
    async def scenario():
        sessions, session, _, _, _, service = _setup_active_player()
        request = JoinRequest(
            "join-reconnect",
            "missing-token",
            STANDARD_GAME_CONFIG,
        )
        with pytest.raises(ReconnectError, match="invalid_session_token"):
            await service.restore(request, object())

        request = JoinRequest(
            "join-reconnect",
            "session-token",
            STANDARD_GAME_CONFIG,
        )
        with pytest.raises(ReconnectError, match="session_already_connected"):
            await service.restore(request, object())

        session.is_connected = False
        session.game_id = None
        session.color = None
        with pytest.raises(ReconnectError, match="reconnect_not_available"):
            await service.restore(request, object())

        assert sessions.get("session-token") is session

    asyncio.run(scenario())


def test_restore_rejects_missing_or_finished_match_and_releases_session():
    async def scenario():
        sessions, session, registry, _, context, service = (
            _setup_active_player()
        )
        registry.remove("game-1")
        session.is_connected = False
        with pytest.raises(ReconnectError, match="game_not_found"):
            await service.restore(
                JoinRequest(
                    "join-reconnect",
                    "session-token",
                    STANDARD_GAME_CONFIG,
                ),
                object(),
            )
        assert sessions.get("session-token") is None

        sessions, session, _, match, context, service = _setup_active_player()
        match.remove_connection(context.connection_id)
        match.finish(
            GameResult(
                PieceColor.BLACK,
                FinishReason.RESIGN,
                100,
            )
        )
        session.is_connected = False
        with pytest.raises(ReconnectError, match="game_already_finished"):
            await service.restore(
                JoinRequest(
                    "join-reconnect",
                    "session-token",
                    STANDARD_GAME_CONFIG,
                ),
                object(),
            )
        assert sessions.get("session-token") is None

    asyncio.run(scenario())


def test_only_one_of_two_simultaneous_reconnects_can_claim_session():
    async def scenario():
        _, session, _, _, context, service = _setup_active_player()
        await service.disconnect(session, context)
        request = JoinRequest(
            "join-reconnect",
            "session-token",
            STANDARD_GAME_CONFIG,
        )

        results = await asyncio.gather(
            service.restore(request, object()),
            service.restore(request, object()),
            return_exceptions=True,
        )

        assert sum(isinstance(result, tuple) for result in results) == 1
        errors = [
            result
            for result in results
            if isinstance(result, ReconnectError)
        ]
        assert len(errors) == 1
        assert errors[0].reason == "session_already_connected"

    asyncio.run(scenario())


def test_failed_admission_leaves_session_available_for_retry():
    class FailingAdmission:
        def restore(self, *_args):
            raise RuntimeError("restore_failed")

    async def scenario():
        sessions, session, registry, match, context, _ = (
            _setup_active_player()
        )
        match.remove_connection(context.connection_id)
        session.is_connected = False
        service = ReconnectService(
            sessions,
            registry,
            FailingAdmission(),
        )

        with pytest.raises(RuntimeError, match="restore_failed"):
            await service.restore(
                JoinRequest(
                    "join-reconnect",
                    "session-token",
                    STANDARD_GAME_CONFIG,
                ),
                object(),
            )

        assert not session.is_connected
        assert sessions.get("session-token") is session

    asyncio.run(scenario())


def test_disconnect_timeout_finishes_paused_match_without_advancing_clock():
    async def no_wait(_seconds):
        return None

    async def scenario():
        sessions, session, registry, match, context, _ = _setup_active_player()
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            grace_period_seconds=20,
            sleep=no_wait,
        )
        opponent = ConnectionContext(
            "opponent",
            "game-1",
            ConnectionRole.PLAYER,
            PieceColor.BLACK,
            user_id=2,
            username="Bob",
            session_token="bob-token",
            websocket=object(),
        )
        match.add_connection(opponent)
        match.advance_time(125)

        assert await service.disconnect(session, context)
        assert match.is_paused
        match.advance_time(5_000)
        assert match.server_time_ms() == 125

        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert match.result == GameResult(
            winner_color=PieceColor.BLACK,
            reason=FinishReason.DISCONNECT,
            duration_ms=125,
        )
        disconnected_message, state_message, game_over_message = _drain(opponent)
        assert decode_event(disconnected_message)["type"] == "PLAYER_DISCONNECTED"
        final_state = decode_state(state_message)
        assert final_state.game_over
        assert final_state.winner_color == "b"
        assert decode_event(game_over_message)["type"] == "GAME_OVER"
        assert sessions.get("session-token") is None

    asyncio.run(scenario())


def test_reconnect_before_timeout_cancels_loss_and_resumes_match():
    sleep_started = asyncio.Event()

    async def waiting_sleep(_seconds):
        sleep_started.set()
        await asyncio.Future()

    # Build this scenario without exposing timing internals through real sleeps.
    async def scenario():
        sessions, session, registry, match, context, _ = _setup_active_player()
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            sleep=waiting_sleep,
        )
        await service.disconnect(session, context)
        await sleep_started.wait()

        await service.restore(
            JoinRequest(
                "join-reconnect",
                "session-token",
                STANDARD_GAME_CONFIG,
            ),
            object(),
        )
        await asyncio.sleep(0)

        assert not match.is_paused
        assert match.result is None
        match.advance_time(50)
        assert match.server_time_ms() == 50
        await service.close()

    asyncio.run(scenario())


def test_spectator_disconnect_and_restore_never_pause_the_match():
    async def waiting_sleep(_seconds):
        await asyncio.Future()

    async def scenario():
        sessions = SessionRegistry(token_factory=lambda: "spectator-token")
        session = sessions.create(3, "Carol", 1200)
        session.game_id = "game-1"
        session.state = SessionState.SPECTATING

        registry = GameRegistry()
        match = Match(
            "game-1",
            GameEngine(create_board(STANDARD_GAME_CONFIG)),
            game_config=STANDARD_GAME_CONFIG,
        )
        registry.add(match)
        original = ConnectionContext(
            "spectator-original",
            "game-1",
            ConnectionRole.SPECTATOR,
            color=None,
            user_id=3,
            username="Carol",
            session_token=session.token,
            websocket=object(),
        )
        match.add_connection(original)
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            sleep=waiting_sleep,
        )

        assert await service.disconnect(session, original)
        assert not match.is_paused
        assert match.result is None

        _, result = await service.restore(
            JoinRequest(
                "join-spectator-reconnect",
                session.token,
                STANDARD_GAME_CONFIG,
            ),
            object(),
        )

        assert result.context.role is ConnectionRole.SPECTATOR
        assert result.context.color is None
        assert session.state is SessionState.SPECTATING
        assert session.is_connected
        assert not match.is_paused
        config_message, state_message = _drain(result.context)
        assert parse_config_response(config_message).effective_config == (
            STANDARD_GAME_CONFIG
        )
        assert decode_state(state_message).role == "SPECTATOR"
        await service.close()

    asyncio.run(scenario())


def test_spectator_reconnect_timeout_only_releases_its_session():
    async def no_wait(_seconds):
        return None

    async def scenario():
        sessions = SessionRegistry(token_factory=lambda: "spectator-token")
        session = sessions.create(3, "Carol", 1200)
        session.game_id = "game-1"
        session.state = SessionState.SPECTATING
        registry = GameRegistry()
        match = Match(
            "game-1",
            GameEngine(create_board(STANDARD_GAME_CONFIG)),
            game_config=STANDARD_GAME_CONFIG,
        )
        registry.add(match)
        context = ConnectionContext(
            "spectator",
            "game-1",
            ConnectionRole.SPECTATOR,
            session_token=session.token,
        )
        match.add_connection(context)
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            sleep=no_wait,
        )

        assert await service.disconnect(session, context)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        assert sessions.get(session.token) is None
        assert match.result is None
        assert not match.is_paused

    asyncio.run(scenario())


def test_reconnect_service_rejects_invalid_grace_period():
    sessions, _, registry, _, _, _ = _setup_active_player()
    with pytest.raises(ValueError, match="INVALID_RECONNECT_GRACE_PERIOD"):
        ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            grace_period_seconds=-1,
        )


def test_repeated_disconnect_replaces_previous_grace_timer():
    async def scenario():
        _, session, _, match, context, service = _setup_active_player()

        assert await service.disconnect(session, context)
        first_timeout = service._timeouts["session-token"]
        assert await service.disconnect(session, context)
        await asyncio.sleep(0)

        assert first_timeout.cancelled()
        assert match.is_paused
        await service.close()

    asyncio.run(scenario())


def test_stale_timeout_and_removed_session_exit_without_finishing_match():
    async def no_wait(_seconds):
        return None

    async def scenario():
        sessions, _, registry, match, _, _ = _setup_active_player()
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            sleep=no_wait,
        )

        await service._expire_after_grace("session-token")

        service._timeouts["session-token"] = asyncio.current_task()
        sessions.release("session-token")
        await service._expire_after_grace("session-token")

        assert match.result is None

    asyncio.run(scenario())


def test_timeout_releases_session_when_match_was_removed_during_grace():
    async def no_wait(_seconds):
        return None

    async def scenario():
        sessions, session, registry, _, _, _ = _setup_active_player()
        service = ReconnectService(
            sessions,
            registry,
            GameAdmission(registry),
            sleep=no_wait,
        )
        sessions.mark_disconnected(session.token)
        registry.remove("game-1")
        service._timeouts[session.token] = asyncio.current_task()

        await service._expire_after_grace(session.token)

        assert sessions.get(session.token) is None

    asyncio.run(scenario())
