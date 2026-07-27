"""Unit tests for atomic server-side session restoration."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG, create_board
from engine.game_engine import GameEngine
from model.game_config import GameConfig
from model.piece import PieceColor
from networking.protocols.game import (
    JoinRequest,
    decode_state,
    parse_config_response,
)
from server.game.admission import GameAdmission
from server.game.game_registry import GameRegistry
from server.game.game_result import FinishReason, GameResult
from server.game.match import Match
from server.services.reconnect import ReconnectError, ReconnectService
from server.services.session_registry import SessionRegistry
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

        config_message, state_message = _drain(result.context)
        config = parse_config_response(config_message)
        state = decode_state(state_message)
        assert config.was_overridden
        assert config.effective_config == STANDARD_GAME_CONFIG
        assert state.game_id == "game-1"
        assert state.assigned_color == "w"
        assert state.player_names["w"] == "Alice"

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
