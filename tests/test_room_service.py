"""Unit tests for room lifecycle coordination and admission reuse."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.piece import PieceColor
from networking.protocols.game import JoinRequest
from server.game.admission import (
    AdmissionPlayer,
    AdmissionResult,
    GameAdmission,
)
from server.game.game_registry import GameRegistry
from server.game.game_result import FinishReason, GameResult
from server.game.room import RoomStatus
from server.game.room_registry import RoomRegistry
from server.services.room_service import (
    RoomCancelledError,
    RoomService,
    RoomServiceError,
)
from server.services.session_registry import ActiveSession, SessionState


def _player(token, user_id):
    session = ActiveSession(token, user_id, token, 1200)
    request = JoinRequest(f"join-{token}", token, STANDARD_GAME_CONFIG)
    return AdmissionPlayer(session, request)


def test_room_service_reuses_game_admission_for_both_players():
    async def scenario():
        game_registry = GameRegistry()
        admission = GameAdmission(
            game_registry,
            game_id_factory=lambda: "room-game",
        )
        room_registry = RoomRegistry()
        service = RoomService(
            room_registry,
            admission.admit_pair,
            room_code_factory=lambda: "AB12",
        )
        creator = _player("creator", 1)
        joiner = _player("joiner", 2)

        waiting = await service.create(creator)
        assert waiting.room.status is RoomStatus.WAITING
        assert creator.session.state is SessionState.WAITING_IN_ROOM

        joiner_result = await service.join("AB12", joiner)
        creator_result = await waiting.admission

        assert creator_result.match is joiner_result.match
        assert waiting.room.match is creator_result.match
        assert waiting.room.status is RoomStatus.ACTIVE
        assert game_registry.get("room-game") is waiting.room.match
        assert creator.session.color is PieceColor.WHITE
        assert joiner.session.color is PieceColor.BLACK
        assert creator.session.state is SessionState.IN_GAME
        assert joiner.session.state is SessionState.IN_GAME
        assert service.waiting_count == 0

    asyncio.run(scenario())


def test_room_service_joins_later_clients_as_spectators():
    async def scenario():
        game_registry = GameRegistry()
        admission = GameAdmission(
            game_registry,
            game_id_factory=lambda: "room-game",
        )
        service = RoomService(
            RoomRegistry(),
            admission.admit_pair,
            room_code_factory=lambda: "AB12",
            spectator_factory=admission.admit_spectator,
        )
        waiting = await service.create(_player("creator", 1))
        await service.join("AB12", _player("joiner", 2))
        spectator = _player("spectator", 3)

        result = await service.join("AB12", spectator)

        assert result.match is waiting.room.match
        assert result.context.color is None
        assert spectator.session.state is SessionState.SPECTATING
        assert len(result.match.connections()) == 3

    asyncio.run(scenario())


def test_room_service_rejects_busy_or_finished_spectators():
    async def scenario():
        admission = GameAdmission(
            GameRegistry(),
            game_id_factory=lambda: "room-game",
        )
        service = RoomService(
            RoomRegistry(),
            admission.admit_pair,
            room_code_factory=lambda: "AB12",
            spectator_factory=admission.admit_spectator,
        )
        waiting = await service.create(_player("creator", 1))
        await service.join("AB12", _player("joiner", 2))

        busy = _player("busy", 3)
        busy.session.state = SessionState.QUEUED
        with pytest.raises(RoomServiceError, match="session_not_available"):
            await service.join("AB12", busy)

        waiting.room.match.finish(
            GameResult(PieceColor.WHITE, FinishReason.RESIGN, 10)
        )
        with pytest.raises(RoomServiceError, match="room_finished"):
            await service.join("AB12", _player("late", 4))

    asyncio.run(scenario())


def test_room_service_translates_spectator_admission_rejection():
    async def scenario():
        admission = GameAdmission(
            GameRegistry(),
            game_id_factory=lambda: "room-game",
        )

        def reject_spectator(_player, _match):
            raise ValueError("SPECTATOR_REJECTED")

        service = RoomService(
            RoomRegistry(),
            admission.admit_pair,
            room_code_factory=lambda: "AB12",
            spectator_factory=reject_spectator,
        )
        await service.create(_player("creator", 1))
        await service.join("AB12", _player("joiner", 2))

        with pytest.raises(RoomServiceError, match="spectator_rejected"):
            await service.join("AB12", _player("spectator", 3))

    asyncio.run(scenario())


def test_room_service_cancels_only_for_the_creator():
    async def scenario():
        registry = RoomRegistry()
        service = RoomService(
            registry,
            lambda *_players: None,
            room_code_factory=lambda: "AB12",
        )
        creator = _player("creator", 1)
        waiting = await service.create(creator)

        with pytest.raises(RoomServiceError, match="room_forbidden"):
            await service.cancel("AB12", "someone-else")

        room = await service.cancel("AB12", creator.session.token)

        assert room.status is RoomStatus.CANCELLED
        assert creator.session.state is SessionState.LOBBY
        assert "AB12" not in registry
        assert service.waiting_count == 0
        with pytest.raises(RoomCancelledError, match="room_cancelled"):
            await waiting.admission

    asyncio.run(scenario())


def test_room_service_rejects_unavailable_missing_active_and_own_room():
    async def scenario():
        registry = RoomRegistry()
        service = RoomService(
            registry,
            lambda *_players: None,
            room_code_factory=lambda: "AB12",
        )
        unavailable = _player("busy", 1)
        unavailable.session.state = SessionState.QUEUED

        with pytest.raises(RoomServiceError, match="session_not_available"):
            await service.create(unavailable)

        creator = _player("creator", 2)
        waiting = await service.create(creator)
        with pytest.raises(RoomServiceError, match="cannot_join_own_room"):
            await service.join("AB12", creator)
        busy_joiner = _player("busy-joiner", 7)
        busy_joiner.session.state = SessionState.QUEUED
        with pytest.raises(RoomServiceError, match="session_not_available"):
            await service.join("AB12", busy_joiner)
        with pytest.raises(RoomServiceError, match="room_not_found"):
            await service.join("ZZ99", _player("missing", 3))

        admission = GameAdmission(GameRegistry())
        replacement = RoomService(
            registry,
            admission.admit_pair,
            room_code_factory=lambda: "CD34",
        )
        joiner = _player("joiner", 4)
        await replacement.create(joiner)
        second = _player("second", 5)
        await replacement.join("CD34", second)

        with pytest.raises(RoomServiceError, match="room_not_waiting"):
            await replacement.join("CD34", _player("late", 6))

        await service.cancel("AB12", creator.session.token)
        with pytest.raises(RoomCancelledError):
            await waiting.admission

    asyncio.run(scenario())


def test_room_service_restores_states_when_pair_creation_fails():
    async def scenario():
        def fail_pairing(_creator, _joiner):
            raise RuntimeError("pair_failed")

        service = RoomService(
            RoomRegistry(),
            fail_pairing,
            room_code_factory=lambda: "AB12",
        )
        creator = _player("creator", 1)
        joiner = _player("joiner", 2)
        waiting = await service.create(creator)

        with pytest.raises(RuntimeError, match="pair_failed"):
            await service.join("AB12", joiner)

        assert creator.session.state is SessionState.WAITING_IN_ROOM
        assert joiner.session.state is SessionState.LOBBY
        assert service.waiting_count == 1

        await service.cancel("AB12", creator.session.token)
        with pytest.raises(RoomCancelledError):
            await waiting.admission

    asyncio.run(scenario())


def test_room_service_rejects_inconsistent_admission_results():
    async def scenario():
        def invalid_pair(first, second):
            return {
                first.session.token: AdmissionResult(None, None),
                second.session.token: AdmissionResult(None, None),
            }

        service = RoomService(
            RoomRegistry(),
            invalid_pair,
            room_code_factory=lambda: "AB12",
        )
        creator = _player("creator", 1)
        waiting = await service.create(creator)

        with pytest.raises(RuntimeError, match="INVALID_ADMISSION_RESULTS"):
            await service.join("AB12", _player("joiner", 2))

        await service.cancel("AB12", creator.session.token)
        with pytest.raises(RoomCancelledError):
            await waiting.admission

    asyncio.run(scenario())


def test_room_service_validates_dependencies_players_and_generated_codes():
    with pytest.raises(TypeError, match="ROOM_REGISTRY_REQUIRED"):
        RoomService(object(), lambda: None)
    with pytest.raises(TypeError, match="PAIR_FACTORY_NOT_CALLABLE"):
        RoomService(RoomRegistry(), None)
    with pytest.raises(TypeError, match="ROOM_CODE_FACTORY_NOT_CALLABLE"):
        RoomService(RoomRegistry(), lambda: None, object())
    with pytest.raises(TypeError, match="SPECTATOR_FACTORY_NOT_CALLABLE"):
        RoomService(
            RoomRegistry(),
            lambda: None,
            spectator_factory=object(),
        )

    async def scenario():
        service = RoomService(
            RoomRegistry(),
            lambda *_players: None,
            room_code_factory=lambda: "bad!",
        )
        with pytest.raises(TypeError, match="ADMISSION_PLAYER_REQUIRED"):
            await service.create(object())
        with pytest.raises(TypeError, match="ADMISSION_PLAYER_REQUIRED"):
            await service.join("AB12", object())
        with pytest.raises(RoomServiceError, match="invalid_room_code"):
            await service.create(_player("creator", 1))

    asyncio.run(scenario())


def test_room_service_default_factory_generates_valid_room_code():
    async def scenario():
        service = RoomService(RoomRegistry(), lambda *_players: None)
        creator = _player("creator", 1)

        waiting = await service.create(creator)

        assert len(waiting.room.room_code) == 6
        assert waiting.room.room_code.isalnum()
        assert waiting.room.room_code == waiting.room.room_code.upper()

        await service.cancel(
            waiting.room.room_code,
            creator.session.token,
        )
        with pytest.raises(RoomCancelledError):
            await waiting.admission

    asyncio.run(scenario())


def test_room_service_retries_collisions_and_rejects_exhaustion():
    async def scenario():
        generated = iter(["AB12", "AB12", "CD34"])
        registry = RoomRegistry()
        service = RoomService(
            registry,
            lambda *_players: None,
            room_code_factory=lambda: next(generated),
        )
        first = await service.create(_player("first", 1))
        second = await service.create(_player("second", 2))

        assert first.room.room_code == "AB12"
        assert second.room.room_code == "CD34"

        await service.close()
        with pytest.raises(RoomCancelledError, match="server_closed"):
            await first.admission
        with pytest.raises(RoomCancelledError, match="server_closed"):
            await second.admission

        full_registry = RoomRegistry()
        full_registry.add(first.room)
        exhausted = RoomService(
            full_registry,
            lambda *_players: None,
            room_code_factory=lambda: "AB12",
        )
        with pytest.raises(RoomServiceError, match="room_code_collision"):
            await exhausted.create(_player("third", 3))

    asyncio.run(scenario())
