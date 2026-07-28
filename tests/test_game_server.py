"""Lifecycle tests for the B3.1 WebSocket listener."""

import asyncio

import pytest
from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from model.position import Position
from networking.protocols.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    encode_register,
    encode_login,
    parse_auth_response,
)
from networking.protocols.game import (
    JoinRequest,
    decode_event,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)
from server.transport.game_server import GameServer
from server.game.game_registry import GameRegistry
from server.services.session_registry import SessionRegistry


PASSWORD = "correct horse battery"


async def _register(websocket, username="Alice", request_id="register-1"):
    """Create an account before the mandatory JOIN handshake."""
    await websocket.send(
        encode_register(RegisterRequest(request_id, username, PASSWORD))
    )
    return parse_auth_response(await websocket.recv())


async def _login(websocket, username="Alice", request_id="login-1"):
    """Authenticate an existing account before the mandatory JOIN handshake."""
    await websocket.send(encode_login(LoginRequest(request_id, username, PASSWORD)))
    return parse_auth_response(await websocket.recv())


async def _send_join(
    websocket,
    username,
    request_id,
    requested_config=STANDARD_GAME_CONFIG,
):
    """Authenticate one socket and place its session in matchmaking."""
    auth_response = await _register(
        websocket,
        username,
        f"register-{request_id}",
    )
    await websocket.send(
        encode_join(
            JoinRequest(
                request_id,
                auth_response.session_token,
                requested_config,
            )
        )
    )
    return auth_response


async def _receive_admission(websocket):
    """Receive the personalized config decision and initial game snapshot."""
    return (
        parse_config_response(await websocket.recv()),
        decode_state(await websocket.recv()),
    )


async def _join_pair(first, second):
    """Queue two authenticated sockets and return both admission results."""
    await _send_join(first, "Alice", "join-first")
    await _send_join(second, "Bob", "join-second")
    return await asyncio.gather(
        _receive_admission(first),
        _receive_admission(second),
    )


def test_game_server_starts_on_ephemeral_port_and_closes(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        assert not server.is_running

        await server.start()
        assert server.is_running
        assert server.bound_port > 0

        await server.close()
        assert not server.is_running

    asyncio.run(scenario())


def test_game_server_rejects_duplicate_start(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            with pytest.raises(RuntimeError, match="server_already_running"):
                await server.start()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_accepts_real_websocket_join(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first, connect(uri) as second:
                await _send_join(first, "Alice", "join-first")
                auth_response = await _register(second, "Bob", "register-second")
                await second.send(
                    encode_join(
                        JoinRequest(
                            "join-second",
                            auth_response.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                (config_response, state), (_, second_state) = await asyncio.gather(
                    _receive_admission(first),
                    _receive_admission(second),
                )

                assert auth_response == AuthResponse(
                    auth_response.request_id,
                    auth_response.user_id,
                    "Bob",
                    1200,
                    auth_response.session_token,
                    20.0,
                )
                assert config_response.was_overridden is False
                assert state.assigned_color == "w"
                assert second_state.assigned_color == "b"
                assert state.game_id == second_state.game_id
                assert state.game_id
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_processes_move_through_reader_and_writer(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket, connect(uri) as opponent:
                await _join_pair(websocket, opponent)
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


def test_game_server_returns_error_for_malformed_command_after_join(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket, connect(uri) as opponent:
                await _join_pair(websocket, opponent)
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


def test_game_server_removes_connection_after_websocket_closes(auth_service):
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
            async with connect(uri) as websocket, connect(uri) as opponent:
                admissions = await _join_pair(websocket, opponent)
                game_id = admissions[0][1].game_id
        finally:
            await server.close()

        assert registry.get(game_id).connections() == ()

    asyncio.run(scenario())


def test_game_server_tick_completes_move_and_sends_arrival_state(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as websocket, connect(uri) as opponent:
                await _join_pair(websocket, opponent)
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


def test_game_server_assigns_authenticated_identity_to_connection_context(
    auth_service,
):
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
            async with connect(uri) as websocket, connect(uri) as opponent:
                auth_response = await _register(websocket, "Alice")
                await websocket.send(
                    encode_join(
                        JoinRequest(
                            "join-first",
                            auth_response.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                await _send_join(opponent, "Bob", "join-second")
                (_, state), _ = await asyncio.gather(
                    _receive_admission(websocket),
                    _receive_admission(opponent),
                )

                context = next(
                    context
                    for context in registry.get(state.game_id).connections()
                    if context.username == "Alice"
                )
                assert context.user_id == auth_response.user_id
                assert context.username == "Alice"
                assert context.session_token == auth_response.session_token
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_rejects_duplicate_active_account(auth_service):
    async def scenario():
        sessions = SessionRegistry()
        server = GameServer(
            port=0,
            session_registry=sessions,
            auth_service=auth_service,
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first:
                await _register(first, "Alice", "register-first")

                async with connect(uri) as second:
                    await second.send(
                        encode_login(LoginRequest("login-second", "alice", PASSWORD))
                    )
                    response = parse_command_response(await second.recv())
                    await asyncio.wait_for(second.wait_closed(), timeout=1.0)

                    assert not response.accepted
                    assert response.request_id == "login-second"
                    assert response.reason == "user_already_connected"
                    assert second.close_code == 1008
                    assert sessions.active_usernames() == ("Alice",)
        finally:
            await server.close()

        assert len(sessions) == 0

    asyncio.run(scenario())


def test_game_server_releases_username_when_join_is_malformed(auth_service):
    async def scenario():
        sessions = SessionRegistry()
        server = GameServer(
            port=0,
            session_registry=sessions,
            auth_service=auth_service,
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first:
                await _register(first, "Alice", "register-first")
                await first.send("NOT_A_JOIN")
                response = parse_command_response(await first.recv())
                await asyncio.wait_for(first.wait_closed(), timeout=1.0)

                assert response.reason == "malformed_join"

            async with connect(uri) as second:
                auth_response = await _login(second, "Alice", "login-second")
                assert auth_response.username == "Alice"
        finally:
            await server.close()

        assert len(sessions) == 0

    asyncio.run(scenario())


def test_game_server_rejects_duplicate_registration(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as first:
                await _register(first, "Alice", "register-first")

            async with connect(uri) as duplicate:
                await duplicate.send(
                    encode_register(
                        RegisterRequest(
                            "register-duplicate",
                            "alice",
                            PASSWORD,
                        )
                    )
                )
                response = parse_command_response(await duplicate.recv())
                await asyncio.wait_for(duplicate.wait_closed(), timeout=1.0)

                assert not response.accepted
                assert response.request_id == "register-duplicate"
                assert response.reason == "username_taken"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_returns_match_timeout_for_waiting_player(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            match_timeout_seconds=0.01,
        )
        await server.start()
        try:
            async with connect(
                f"ws://127.0.0.1:{server.bound_port}"
            ) as websocket:
                await _send_join(websocket, "Alice", "join-timeout")

                response = parse_command_response(await websocket.recv())
                await asyncio.wait_for(websocket.wait_closed(), timeout=1.0)

                assert not response.accepted
                assert response.request_id == "join-timeout"
                assert response.reason == "match_timeout"
                assert websocket.close_code == 1008
                assert server._matchmaker.waiting_count == 0
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_removes_player_who_disconnects_while_waiting(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            match_timeout_seconds=1.0,
        )
        await server.start()
        websocket = await connect(f"ws://127.0.0.1:{server.bound_port}")
        try:
            await _send_join(websocket, "Alice", "join-disconnect")
            deadline = asyncio.get_running_loop().time() + 1.0
            while server._matchmaker.waiting_count != 1:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("player did not enter matchmaking")
                await asyncio.sleep(0.01)

            await websocket.close()
            while server._matchmaker.waiting_count:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("disconnected player remained queued")
                await asyncio.sleep(0.01)

            assert server._matchmaker.waiting_count == 0
        finally:
            await websocket.close()
            await server.close()

    asyncio.run(scenario())


def test_game_server_restores_disconnected_player_through_regular_join(
    auth_service,
):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        uri = f"ws://127.0.0.1:{server.bound_port}"
        first = await connect(uri)
        second = await connect(uri)
        restored = duplicate = invalid = None
        try:
            first_auth = await _send_join(first, "Alice", "join-first")
            await _send_join(second, "Bob", "join-second")
            (first_admission, _) = await asyncio.gather(
                _receive_admission(first),
                _receive_admission(second),
            )
            original_state = first_admission[1]

            await first.close()
            deadline = asyncio.get_running_loop().time() + 1.0
            while True:
                session = server._sessions.get(first_auth.session_token)
                if session is not None and not session.is_connected:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("session was not retained after disconnect")
                await asyncio.sleep(0.01)

            restored = await connect(uri)
            await restored.send(
                encode_join(
                    JoinRequest(
                        "join-restored",
                        first_auth.session_token,
                        STANDARD_GAME_CONFIG,
                    )
                )
            )
            restored_config, restored_state = await _receive_admission(restored)

            assert not restored_config.was_overridden
            assert restored_state.game_id == original_state.game_id
            assert restored_state.assigned_color == "w"
            assert restored_state.player_names == {
                "w": "Alice",
                "b": "Bob",
            }

            duplicate = await connect(uri)
            await duplicate.send(
                encode_join(
                    JoinRequest(
                        "join-duplicate",
                        first_auth.session_token,
                        STANDARD_GAME_CONFIG,
                    )
                )
            )
            duplicate_response = parse_command_response(
                await duplicate.recv()
            )
            assert duplicate_response.reason == "session_already_connected"

            invalid = await connect(uri)
            await invalid.send(
                encode_join(
                    JoinRequest(
                        "join-invalid",
                        "missing-token",
                        STANDARD_GAME_CONFIG,
                    )
                )
            )
            invalid_response = parse_command_response(await invalid.recv())
            assert invalid_response.reason == "invalid_session_token"
        finally:
            for websocket in (first, second, restored, duplicate, invalid):
                if websocket is not None:
                    await websocket.close()
            await server.close()

    asyncio.run(scenario())


def test_game_server_rejects_join_token_different_from_authenticated_session(
    auth_service,
):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            async with connect(
                f"ws://127.0.0.1:{server.bound_port}"
            ) as websocket:
                await _register(websocket, "Alice", "register-mismatch")
                await websocket.send(
                    encode_join(
                        JoinRequest(
                            "join-mismatch",
                            "another-token",
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )

                response = parse_command_response(await websocket.recv())
                assert response.request_id == "join-mismatch"
                assert response.reason == "invalid_session_token"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_game_server_rejects_malformed_direct_join(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        try:
            async with connect(
                f"ws://127.0.0.1:{server.bound_port}"
            ) as websocket:
                await websocket.send("JOIN malformed")
                response = parse_command_response(await websocket.recv())
                await asyncio.wait_for(websocket.wait_closed(), timeout=1.0)

                assert response.request_id == "0"
                assert not response.accepted
                assert response.reason == "malformed_join"
                assert websocket.close_code == 1008
        finally:
            await server.close()

    asyncio.run(scenario())
