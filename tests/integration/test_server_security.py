"""Real-WebSocket integration tests for admission and command authorization."""

import asyncio

from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.game_config import GameConfig
from model.position import Position
from networking.protocol import (
    JoinRequest,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)
from server.game.game_registry import GameRegistry
from server.transport.game_server import GameServer


async def _join(websocket, request_id, requested_config=STANDARD_GAME_CONFIG):
    """Send JOIN and return the server's config decision and initial state."""
    await websocket.send(encode_join(JoinRequest(request_id, requested_config)))
    decision = parse_config_response(await websocket.recv())
    state = decode_state(await websocket.recv())
    return decision, state


async def _receive_responses(websocket, expected_ids, timeout=2.0):
    """Ignore asynchronous state/events until every expected response arrives."""
    responses = {}
    deadline = asyncio.get_running_loop().time() + timeout
    while responses.keys() != expected_ids:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("expected command responses were not received")
        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
        if message.startswith(("OK ", "ERR ")):
            response = parse_command_response(message)
            if response.request_id in expected_ids:
                responses[response.request_id] = response
    return responses


def test_black_client_cannot_forge_white_move_over_websocket():
    async def scenario():
        registry = GameRegistry()
        server = GameServer(port=0, registry=registry)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as white, connect(uri) as black:
                await _join(white, "join-white")
                await _join(black, "join-black")

                await black.send("MOVE forged-white WPe2e3")
                responses = await _receive_responses(black, {"forged-white"})

                assert not responses["forged-white"].accepted
                assert responses["forged-white"].reason == "wrong_color"
                authoritative = registry.get("default").engine.snapshot()
                white_pawn = next(
                    piece for piece in authoritative.pieces if piece.cell == Position(6, 4)
                )
                assert white_pawn.color == "w"
                assert authoritative.active_motions == []
        finally:
            await server.close()

    asyncio.run(scenario())


def test_third_websocket_client_is_rejected_as_server_full():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first, connect(uri) as second:
                await _join(first, "join-first")
                await _join(second, "join-second")

                async with connect(uri) as third:
                    await third.send(encode_join(
                        JoinRequest("join-third", STANDARD_GAME_CONFIG)
                    ))
                    response = parse_command_response(await third.recv())
                    await asyncio.wait_for(third.wait_closed(), timeout=1.0)

                    assert response.request_id == "join-third"
                    assert not response.accepted
                    assert response.reason == "server_full"
                    assert third.close_code == 1008
        finally:
            await server.close()

    asyncio.run(scenario())


def test_second_client_receives_authoritative_config_override_over_websocket():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first, connect(uri) as second:
                await _join(first, "join-first")
                requested = GameConfig(1, 10, 10, "standard")

                decision, state = await _join(second, "join-second", requested)

                assert decision.was_overridden
                assert decision.effective_config == STANDARD_GAME_CONFIG
                assert (state.board_height, state.board_width) == (8, 8)
                assert state.assigned_color == "b"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_interleaved_messages_preserve_command_request_ids():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket:
                await _join(websocket, "join-white")

                await websocket.send("MOVE move-request WPe2e3")
                await websocket.send("JUMP jump-request WPe2")
                responses = await _receive_responses(
                    websocket,
                    {"move-request", "jump-request"},
                )

                assert responses["move-request"].accepted
                assert not responses["jump-request"].accepted
                assert responses["jump-request"].reason == "motion_in_progress"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_malformed_initial_join_is_rejected_and_socket_is_closed():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket:
                await websocket.send("NOT_A_JOIN")
                response = parse_command_response(await websocket.recv())
                await asyncio.wait_for(websocket.wait_closed(), timeout=1.0)

                assert response.request_id == "0"
                assert not response.accepted
                assert response.reason == "malformed_join"
                assert websocket.close_code == 1008
        finally:
            await server.close()

    asyncio.run(scenario())
