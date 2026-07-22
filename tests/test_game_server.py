"""Lifecycle tests for the B3.1 WebSocket listener."""

import asyncio

import pytest
from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.position import Position
from networking.protocol import (
    JoinRequest,
    decode_event,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)
from server.transport.game_server import GameServer
from server.game.game_registry import GameRegistry


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


def test_game_server_processes_move_through_reader_and_writer():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            async with connect(f"ws://127.0.0.1:{server.bound_port}") as websocket:
                await websocket.send(encode_join(JoinRequest("join-1", STANDARD_GAME_CONFIG)))
                parse_config_response(await websocket.recv())
                decode_state(await websocket.recv())

                await websocket.send("MOVE move-1 WPe2e3")
                event_message = state_message = response_message = None
                while None in (event_message, state_message, response_message):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    if message.startswith("EVENT ") and decode_event(message)["type"] == "MOTION":
                        event_message = message
                    elif message.startswith("STATE ") and decode_state(message).active_motions:
                        state_message = message
                    elif message.startswith(("OK ", "ERR ")):
                        response_message = message

                assert decode_event(event_message)["type"] == "MOTION"
                assert len(decode_state(state_message).active_motions) == 1
                response = parse_command_response(response_message)
                assert response.accepted is True
                assert response.request_id == "move-1"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_returns_error_for_malformed_command_after_join():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            async with connect(f"ws://127.0.0.1:{server.bound_port}") as websocket:
                await websocket.send(encode_join(JoinRequest("join-1", STANDARD_GAME_CONFIG)))
                await websocket.recv()
                await websocket.recv()

                await websocket.send("NOT_A_COMMAND")

                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                while not message.startswith(("OK ", "ERR ")):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                response = parse_command_response(message)
                assert response.accepted is False
                assert response.request_id == "0"
                assert response.reason == "MALFORMED_COMMAND"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_removes_connection_after_websocket_closes():
    async def scenario():
        registry = GameRegistry()
        server = GameServer(port=0, registry=registry)
        await server.start()
        try:
            async with connect(f"ws://127.0.0.1:{server.bound_port}") as websocket:
                await websocket.send(encode_join(JoinRequest("join-1", STANDARD_GAME_CONFIG)))
                await websocket.recv()
                await websocket.recv()
        finally:
            await server.close()

        assert registry.get("default").connections() == ()

    asyncio.run(scenario())


def test_game_server_tick_completes_move_and_sends_arrival_state():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            async with connect(f"ws://127.0.0.1:{server.bound_port}") as websocket:
                await websocket.send(encode_join(JoinRequest("join-1", STANDARD_GAME_CONFIG)))
                await websocket.recv()
                await websocket.recv()
                await websocket.send("MOVE timed-move WPe2e3")

                saw_arrival = False
                saw_final_state = False
                while not (saw_arrival and saw_final_state):
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    if message.startswith("EVENT "):
                        saw_arrival = saw_arrival or decode_event(message)["type"] == "ARRIVAL"
                    elif message.startswith("STATE "):
                        state = decode_state(message)
                        pawn = next(
                            (piece for piece in state.pieces if piece.cell == Position(5, 4)),
                            None,
                        )
                        saw_final_state = pawn is not None and not state.active_motions

                assert saw_arrival
                assert saw_final_state
        finally:
            await server.close()

    asyncio.run(scenario())
