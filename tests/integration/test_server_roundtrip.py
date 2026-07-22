"""End-to-end WebSocket test across the real server and two real clients."""

import asyncio

from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.position import Position
from networking.login_protocol import LoginRequest, encode_login, parse_login_response
from networking.protocol import (
    JoinRequest,
    decode_event,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)
from server.transport.game_server import GameServer


async def _join(websocket, request_id):
    """Complete the mandatory handshake and return the initial snapshot."""
    username = request_id.replace("join", "user")
    await websocket.send(encode_login(LoginRequest(f"login-{username}", username)))
    parse_login_response(await websocket.recv())
    await websocket.send(encode_join(JoinRequest(request_id, STANDARD_GAME_CONFIG)))
    config_response = parse_config_response(await websocket.recv())
    initial_state = decode_state(await websocket.recv())
    return config_response, initial_state


async def _observe_completed_move(websocket, request_id=None):
    """Wait for the move's arrival and final board, plus OK for its sender."""
    arrival_seen = False
    final_state = None
    response = None
    deadline = asyncio.get_running_loop().time() + 3.0

    while not (
        arrival_seen
        and final_state is not None
        and (request_id is None or response is not None)
    ):
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("move round-trip did not complete")
        message = await asyncio.wait_for(websocket.recv(), timeout=remaining)

        if message.startswith("EVENT "):
            arrival_seen = arrival_seen or decode_event(message)["type"] == "ARRIVAL"
        elif message.startswith("STATE "):
            state = decode_state(message)
            pawn_at_e3 = any(piece.cell == Position(5, 4) for piece in state.pieces)
            if pawn_at_e3 and not state.active_motions:
                final_state = state
        elif request_id is not None and message.startswith(("OK ", "ERR ")):
            candidate = parse_command_response(message)
            if candidate.request_id == request_id:
                response = candidate

    return response, final_state


def _board_signature(state):
    """Compare shared game data while ignoring connection-specific metadata."""
    return tuple(
        sorted((piece.id, piece.cell.row, piece.cell.col, piece.state) for piece in state.pieces)
    )


def test_two_clients_share_one_authoritative_websocket_game():
    async def scenario():
        server = GameServer(port=0)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as white, connect(uri) as black:
                white_config, white_initial = await _join(white, "join-white")
                black_config, black_initial = await _join(black, "join-black")
                white_after_black_joined = decode_state(await white.recv())

                assert not white_config.was_overridden
                assert not black_config.was_overridden
                assert white_initial.assigned_color == "w"
                assert black_initial.assigned_color == "b"
                assert white_after_black_joined.player_names == {
                    "w": "user-white",
                    "b": "user-black",
                }
                assert black_initial.player_names == white_after_black_joined.player_names
                assert _board_signature(white_initial) == _board_signature(black_initial)

                await white.send("MOVE move-white WPe2e3")
                (white_response, white_final), (_, black_final) = await asyncio.gather(
                    _observe_completed_move(white, "move-white"),
                    _observe_completed_move(black),
                )

                assert white_response.accepted
                assert white_final.game_id == black_final.game_id == "default"
                assert _board_signature(white_final) == _board_signature(black_final)
        finally:
            await server.close()

    asyncio.run(scenario())
