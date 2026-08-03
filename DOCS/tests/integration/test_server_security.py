"""Real-WebSocket integration tests for admission and command authorization."""

import asyncio

from websockets.asyncio.client import connect

from networking.models.standard_game_config import STANDARD_GAME_CONFIG
from networking.models.game_config import GameConfig
from networking.models.position import Position
from networking.protocols.auth import (
    RegisterRequest,
    encode_register,
    parse_auth_response,
)
from networking.protocols.game import (
    JoinRequest,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)
from server.game.game_registry import GameRegistry
from server.transport.game_server import GameServer


PASSWORD = "correct horse battery"


async def _send_join(websocket, request_id, requested_config=STANDARD_GAME_CONFIG):
    """Authenticate and place one real socket in matchmaking."""
    username = request_id.replace("join", "user")
    await websocket.send(
        encode_register(
            RegisterRequest(f"register-{username}", username, PASSWORD)
        )
    )
    auth_response = parse_auth_response(await websocket.recv())
    await websocket.send(encode_join(
        JoinRequest(
            request_id,
            auth_response.session_token,
            requested_config,
        )
    ))


async def _receive_admission(websocket):
    """Receive a decision and snapshot after a compatible opponent arrives."""
    decision = parse_config_response(await websocket.recv())
    state = decode_state(await websocket.recv())
    return decision, state


async def _join_pair(
    first,
    second,
    first_config=STANDARD_GAME_CONFIG,
    second_config=STANDARD_GAME_CONFIG,
    first_id="join-first",
    second_id="join-second",
):
    """Admit two sockets into one newly created match."""
    await _send_join(first, first_id, first_config)
    await _send_join(second, second_id, second_config)
    return await asyncio.gather(
        _receive_admission(first),
        _receive_admission(second),
    )


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


def test_black_client_cannot_forge_white_move_over_websocket(auth_service):
    async def scenario():
        registry = GameRegistry()
        server = GameServer(
            port=0,
            registry=registry,
            auth_service=auth_service,
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as white, connect(uri) as black:
                admissions = await _join_pair(
                    white,
                    black,
                    first_id="join-white",
                    second_id="join-black",
                )

                await black.send("MOVE forged-white WPe2e3")
                responses = await _receive_responses(black, {"forged-white"})

                assert not responses["forged-white"].accepted
                assert responses["forged-white"].reason == "wrong_color"
                game_id = admissions[0][1].game_id
                authoritative = registry.get(game_id).engine.snapshot()
                white_pawn = next(
                    piece for piece in authoritative.pieces if piece.cell == Position(6, 4)
                )
                assert white_pawn.color == "w"
                assert authoritative.active_motions == []
        finally:
            await server.close()

    asyncio.run(scenario())


def test_four_clients_are_split_into_two_isolated_matches(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with (
                connect(uri) as first,
                connect(uri) as second,
                connect(uri) as third,
                connect(uri) as fourth,
            ):
                first_pair = await _join_pair(first, second)
                second_pair = await _join_pair(
                    third,
                    fourth,
                    first_id="join-third",
                    second_id="join-fourth",
                )

                first_game_ids = {result[1].game_id for result in first_pair}
                second_game_ids = {result[1].game_id for result in second_pair}
                assert len(first_game_ids) == len(second_game_ids) == 1
                assert first_game_ids.isdisjoint(second_game_ids)
                assert len(server._registry) == 2
        finally:
            await server.close()

    asyncio.run(scenario())


def test_unsupported_config_is_rejected_without_removing_waiting_player(
    auth_service,
):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with (
                connect(uri) as first,
                connect(uri) as rejected,
                connect(uri) as replacement,
            ):
                requested = GameConfig(1, 10, 10, "standard")
                await _send_join(first, "join-first")
                await _send_join(rejected, "join-rejected", requested)

                rejection = parse_command_response(await rejected.recv())
                await asyncio.wait_for(rejected.wait_closed(), timeout=1.0)
                assert not rejection.accepted
                assert rejection.request_id == "join-rejected"
                assert rejection.reason == "unsupported_game_config"

                await _send_join(replacement, "join-replacement")
                (first_result, replacement_result) = await asyncio.gather(
                    _receive_admission(first),
                    _receive_admission(replacement),
                )
                assert first_result[1].game_id == replacement_result[1].game_id
                assert replacement_result[1].assigned_color == "b"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_interleaved_messages_preserve_command_request_ids(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket, connect(uri) as opponent:
                await _join_pair(
                    websocket,
                    opponent,
                    first_id="join-white",
                    second_id="join-black",
                )

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


def test_join_before_authentication_is_rejected_and_socket_is_closed(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket:
                await websocket.send("NOT_A_JOIN")
                response = parse_command_response(await websocket.recv())
                await asyncio.wait_for(websocket.wait_closed(), timeout=1.0)

                assert response.request_id == "0"
                assert not response.accepted
                assert response.reason == "malformed_auth_request"
                assert websocket.close_code == 1008
        finally:
            await server.close()

    asyncio.run(scenario())
