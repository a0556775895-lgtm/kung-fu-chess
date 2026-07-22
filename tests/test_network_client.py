"""Tests for the threaded client transport against a real WebSocket server."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocol import decode_event, parse_command_response
from client.network_client import NetworkClient
from server.game.game_registry import GameRegistry
from server.transport.game_server import GameServer


async def _start_client(server):
    client = NetworkClient(f"ws://127.0.0.1:{server.bound_port}")
    await asyncio.to_thread(client.start)
    return client


async def _wait_for_messages(client, predicate, timeout=2.0):
    messages = []
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate(messages):
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("expected client messages were not received")
        messages.extend(client.drain_messages())
        await asyncio.sleep(0.01)
    return messages


def test_network_client_completes_join_before_start_returns():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        client = None
        try:
            client = await _start_client(server)

            assert client.is_connected
            assert client.config_response.effective_config == STANDARD_GAME_CONFIG
            assert not client.config_response.was_overridden
            assert client.initial_state.assigned_color == "w"
            assert client.initial_state.game_id == "default"
        finally:
            if client is not None:
                await asyncio.to_thread(client.close)
            await server.close()

    asyncio.run(scenario())


def test_network_client_sends_command_and_receives_server_messages():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        client = None
        try:
            client = await _start_client(server)
            client.send("MOVE client-move WPe2e3")

            def received_response_and_motion(messages):
                has_response = any(
                    message.startswith(("OK ", "ERR "))
                    and parse_command_response(message).request_id == "client-move"
                    for message in messages
                )
                has_motion = any(
                    message.startswith("EVENT ")
                    and decode_event(message)["type"] == "MOTION"
                    for message in messages
                )
                return has_response and has_motion

            messages = await _wait_for_messages(client, received_response_and_motion)
            response_message = next(
                message
                for message in messages
                if message.startswith(("OK ", "ERR "))
                and parse_command_response(message).request_id == "client-move"
            )

            assert parse_command_response(response_message).accepted
        finally:
            if client is not None:
                await asyncio.to_thread(client.close)
            await server.close()

    asyncio.run(scenario())


def test_network_client_close_releases_server_connection():
    async def scenario():
        registry = GameRegistry()
        server = GameServer(port=0, registry=registry)
        await server.start()
        client = None
        try:
            client = await _start_client(server)
            assert len(registry.get("default").connections()) == 1

            await asyncio.to_thread(client.close)
            assert not client.is_connected

            deadline = asyncio.get_running_loop().time() + 1.0
            while registry.get("default").connections():
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("server did not release the client")
                await asyncio.sleep(0.01)

            with pytest.raises(RuntimeError, match="client_not_connected"):
                client.send("MOVE after-close WPe2e3")
        finally:
            if client is not None and client.is_connected:
                await asyncio.to_thread(client.close)
            await server.close()

    asyncio.run(scenario())
