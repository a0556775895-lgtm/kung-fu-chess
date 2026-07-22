"""Lifecycle tests for the B3.1 WebSocket listener."""

import asyncio

import pytest
from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocol import (
    JoinRequest,
    decode_state,
    encode_join,
    parse_config_response,
)
from server.transport.game_server import GameServer


def test_game_server_starts_on_ephemeral_port_and_closes():
    async def scenario():
        server = GameServer(port=0)
        assert not server.is_running

        await server.start()
        assert server.is_running
        assert server.bound_port > 0

        await server.close()
        assert not server.is_running

    asyncio.run(scenario())


def test_game_server_rejects_duplicate_start():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            with pytest.raises(RuntimeError, match="server_already_running"):
                await server.start()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_accepts_real_websocket_join():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            async with connect(f"ws://127.0.0.1:{server.bound_port}") as websocket:
                await websocket.send(encode_join(JoinRequest("join-1", STANDARD_GAME_CONFIG)))

                config_response = parse_config_response(await websocket.recv())
                state = decode_state(await websocket.recv())

                assert config_response.was_overridden is False
                assert state.assigned_color == "w"
                assert state.game_id == "default"
        finally:
            await server.close()

    asyncio.run(scenario())
