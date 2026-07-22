"""In-memory tests for atomic player admission and config selection."""

import asyncio

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.game_config import GameConfig
from model.piece import PieceColor
from networking.protocol import (
    JoinRequest,
    decode_state,
    parse_command_response,
    parse_config_response,
)
from server.game.admission import GameAdmission
from server.game.game_registry import GameRegistry


def _admission_with_predictable_ids():
    ids = iter(("connection-1", "connection-2", "connection-3"))
    registry = GameRegistry()
    return registry, GameAdmission(registry, connection_id_factory=lambda: next(ids))


def _drain(context):
    return [context.outbound.get_nowait() for _ in range(context.outbound.qsize())]


def test_first_player_creates_match_and_receives_white():
    async def scenario():
        registry, admission = _admission_with_predictable_ids()

        result = await admission.admit(JoinRequest("join-1", STANDARD_GAME_CONFIG))

        assert result.is_accepted
        assert result.context.color is PieceColor.WHITE
        assert len(registry) == 1
        config_message, state_message = _drain(result.context)
        assert parse_config_response(config_message).was_overridden is False
        state = decode_state(state_message)
        assert state.assigned_color == "w"
        assert (state.board_height, state.board_width) == (8, 8)

    asyncio.run(scenario())


def test_second_player_receives_black_and_match_config_override():
    async def scenario():
        _, admission = _admission_with_predictable_ids()
        first = await admission.admit(JoinRequest("join-1", STANDARD_GAME_CONFIG))
        _drain(first.context)
        requested = GameConfig(1, 10, 10, "standard")

        second = await admission.admit(JoinRequest("join-2", requested))

        assert second.context.color is PieceColor.BLACK
        config_message, state_message = _drain(second.context)
        decision = parse_config_response(config_message)
        assert decision.was_overridden is True
        assert decision.effective_config == STANDARD_GAME_CONFIG
        assert decode_state(state_message).assigned_color == "b"

    asyncio.run(scenario())


def test_third_player_is_rejected_as_server_full():
    async def scenario():
        _, admission = _admission_with_predictable_ids()
        await admission.admit(JoinRequest("join-1", STANDARD_GAME_CONFIG))
        await admission.admit(JoinRequest("join-2", STANDARD_GAME_CONFIG))

        third = await admission.admit(JoinRequest("join-3", STANDARD_GAME_CONFIG))

        assert not third.is_accepted
        response = parse_command_response(third.rejection)
        assert response.reason == "server_full"

    asyncio.run(scenario())


def test_first_player_with_unsupported_config_is_rejected_without_match():
    async def scenario():
        registry, admission = _admission_with_predictable_ids()
        unsupported = GameConfig(1, 10, 10, "standard")

        result = await admission.admit(JoinRequest("join-1", unsupported))

        assert not result.is_accepted
        assert parse_command_response(result.rejection).reason == "unsupported_game_config"
        assert len(registry) == 0

    asyncio.run(scenario())


def test_concurrent_joins_receive_distinct_colors():
    async def scenario():
        _, admission = _admission_with_predictable_ids()
        first, second = await asyncio.gather(
            admission.admit(JoinRequest("join-1", STANDARD_GAME_CONFIG)),
            admission.admit(JoinRequest("join-2", STANDARD_GAME_CONFIG)),
        )

        assert {first.context.color, second.context.color} == {
            PieceColor.WHITE,
            PieceColor.BLACK,
        }

    asyncio.run(scenario())


def test_released_color_can_be_assigned_again():
    async def scenario():
        _, admission = _admission_with_predictable_ids()
        first = await admission.admit(JoinRequest("join-1", STANDARD_GAME_CONFIG))
        admission.release(first.context)

        replacement = await admission.admit(JoinRequest("join-2", STANDARD_GAME_CONFIG))

        assert replacement.context.color is PieceColor.WHITE

    asyncio.run(scenario())
