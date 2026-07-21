"""Lifecycle tests for the B3.1 WebSocket listener."""

import asyncio

import pytest

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
