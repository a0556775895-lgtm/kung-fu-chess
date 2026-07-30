"""Tests for the threaded client transport against a real WebSocket server."""

import asyncio

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocols.game import decode_event, parse_command_response
from client.network_client import (
    AuthenticationRejectedError,
    ConnectionState,
    MatchmakingTimeoutError,
    NetworkClient,
)
from server.game.game_registry import GameRegistry
from server.transport.game_server import GameServer


PASSWORD = "correct horse battery"


async def _start_client(server, username="Alice", *, register=True, password=PASSWORD):
    client = NetworkClient(
        f"ws://127.0.0.1:{server.bound_port}",
        username,
        password,
        register=register,
    )
    await asyncio.to_thread(client.start)
    return client


async def _start_pair(server, *, register=True):
    """Start two clients concurrently because each waits for matchmaking."""
    first = NetworkClient(
        f"ws://127.0.0.1:{server.bound_port}",
        "Alice",
        PASSWORD,
        register=register,
        match_timeout=2.0,
    )
    second = NetworkClient(
        f"ws://127.0.0.1:{server.bound_port}",
        "Bob",
        PASSWORD,
        register=register,
        match_timeout=2.0,
    )
    await asyncio.gather(
        asyncio.to_thread(first.start),
        asyncio.to_thread(second.start),
    )
    return first, second


async def _close_clients(*clients):
    """Close every started client without repeating thread cleanup in tests."""
    await asyncio.gather(
        *(
            asyncio.to_thread(client.close)
            for client in clients
            if client is not None
        )
    )


async def _wait_for_messages(client, predicate, timeout=2.0):
    messages = []
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate(messages):
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("expected client messages were not received")
        messages.extend(client.drain_messages())
        await asyncio.sleep(0.01)
    return messages


async def _wait_for_client_state(client, expected, timeout=2.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while client.connection_status.state is not expected:
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"client did not reach {expected.value}")
        await asyncio.sleep(0.01)


async def _authenticate_client(server, username):
    client = NetworkClient(
        f"ws://127.0.0.1:{server.bound_port}",
        username,
        PASSWORD,
        register=True,
    )
    await asyncio.to_thread(client.authenticate)
    return client


def test_network_client_completes_join_before_start_returns(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        client = opponent = None
        try:
            client, opponent = await _start_pair(server)

            assert client.is_connected
            assert client.auth_response.username == "Alice"
            assert client.auth_response.rating == 1200
            assert client.session_token == client.auth_response.session_token
            assert client.config_response.effective_config == STANDARD_GAME_CONFIG
            assert not client.config_response.was_overridden
            assert {
                client.initial_state.assigned_color,
                opponent.initial_state.assigned_color,
            } == {"w", "b"}
            assert client.initial_state.game_id == opponent.initial_state.game_id
        finally:
            await _close_clients(client, opponent)
            await server.close()

    asyncio.run(scenario())


def test_network_client_authenticates_without_starting_matchmaking(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        client = None
        try:
            client = await _authenticate_client(server, "Alice")

            assert client.auth_response.username == "Alice"
            assert client.connection_status.state is ConnectionState.LOBBY
            assert not client.is_connected
            assert client.room_code is None
            assert client.lobby_error is None
        finally:
            await _close_clients(client)
            await server.close()

    asyncio.run(scenario())


def test_network_clients_create_and_join_room_before_game(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        creator = joiner = None
        try:
            creator, joiner = await asyncio.gather(
                _authenticate_client(server, "Alice"),
                _authenticate_client(server, "Bob"),
            )

            creator.create_room()
            await _wait_for_client_state(
                creator,
                ConnectionState.WAITING_IN_ROOM,
            )
            deadline = asyncio.get_running_loop().time() + 2.0
            while creator.room_code is None:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("creator did not receive room code")
                await asyncio.sleep(0.01)

            joiner.join_room(creator.room_code)
            await asyncio.gather(
                asyncio.to_thread(creator.wait_for_game, 2.0),
                asyncio.to_thread(joiner.wait_for_game, 2.0),
            )

            assert creator.is_connected
            assert joiner.is_connected
            assert creator.room_code == joiner.room_code == "AB12"
            assert creator.initial_state.assigned_color == "w"
            assert joiner.initial_state.assigned_color == "b"
            assert (
                creator.initial_state.game_id
                == joiner.initial_state.game_id
            )
        finally:
            await _close_clients(creator, joiner)
            await server.close()

    asyncio.run(scenario())


def test_network_client_cancels_room_and_returns_to_lobby(auth_service):
    async def scenario():
        generated_codes = iter(("AB12", "CD34"))
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: next(generated_codes),
        )
        await server.start()
        creator = None
        try:
            creator = await _authenticate_client(server, "Alice")

            creator.create_room()
            deadline = asyncio.get_running_loop().time() + 2.0
            while creator.room_code != "AB12":
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("first room was not created")
                await asyncio.sleep(0.01)

            creator.cancel_room()
            await _wait_for_client_state(creator, ConnectionState.LOBBY)

            assert creator.room_code is None
            assert creator.lobby_error is None

            creator.create_room()
            deadline = asyncio.get_running_loop().time() + 2.0
            while creator.room_code != "CD34":
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("second room was not created")
                await asyncio.sleep(0.01)
        finally:
            await _close_clients(creator)
            await server.close()

    asyncio.run(scenario())


def test_network_client_recovers_from_missing_room(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        client = None
        try:
            client = await _authenticate_client(server, "Alice")

            client.join_room("ZZ99")
            await _wait_for_client_state(client, ConnectionState.LOBBY)

            assert client.lobby_error == "room_not_found"
            assert client.room_code is None
        finally:
            await _close_clients(client)
            await server.close()

    asyncio.run(scenario())


def test_network_client_reports_duplicate_active_account(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        first = opponent = None
        try:
            first, opponent = await _start_pair(server)
            duplicate = NetworkClient(
                f"ws://127.0.0.1:{server.bound_port}",
                "alice",
                PASSWORD,
            )

            with pytest.raises(
                AuthenticationRejectedError,
                match="user_already_connected",
            ):
                await asyncio.to_thread(duplicate.start)

            assert first.is_connected
            assert not duplicate.is_connected
        finally:
            await _close_clients(first, opponent)
            await server.close()

    asyncio.run(scenario())


def test_network_client_sends_command_and_receives_server_messages(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        client = opponent = None
        try:
            client, opponent = await _start_pair(server)
            white_client = next(
                candidate
                for candidate in (client, opponent)
                if candidate.initial_state.assigned_color == "w"
            )
            white_client.send("MOVE client-move WPe2e3")

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

            messages = await _wait_for_messages(
                white_client,
                received_response_and_motion,
            )
            response_message = next(
                message
                for message in messages
                if message.startswith(("OK ", "ERR "))
                and parse_command_response(message).request_id == "client-move"
            )

            assert parse_command_response(response_message).accepted
        finally:
            await _close_clients(client, opponent)
            await server.close()

    asyncio.run(scenario())


def test_network_client_close_releases_server_connection(auth_service):
    async def scenario():
        registry = GameRegistry()
        server = GameServer(
            port=0,
            registry=registry,
            auth_service=auth_service,
        )
        await server.start()
        client = opponent = None
        try:
            client, opponent = await _start_pair(server)
            game_id = client.initial_state.game_id
            assert len(registry.get(game_id).connections()) == 2

            await asyncio.to_thread(client.close)
            assert not client.is_connected

            deadline = asyncio.get_running_loop().time() + 1.0
            while len(registry.get(game_id).connections()) != 1:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("server did not release the client")
                await asyncio.sleep(0.01)

            with pytest.raises(RuntimeError, match="client_not_connected"):
                client.send("MOVE after-close WPe2e3")
        finally:
            await _close_clients(client, opponent)
            await server.close()

    asyncio.run(scenario())


def test_network_client_blocks_login_while_disconnected_session_is_reserved(
    auth_service,
):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        registered = registered_opponent = None
        try:
            registered, registered_opponent = await _start_pair(server)
            await _close_clients(registered, registered_opponent)

            with pytest.raises(
                AuthenticationRejectedError,
                match="user_already_connected",
            ):
                await _start_client(server, register=False)
        finally:
            await server.close()

    asyncio.run(scenario())


def test_network_client_rejects_wrong_password(auth_service):
    async def scenario():
        server = GameServer(port=0, auth_service=auth_service)
        await server.start()
        registered = opponent = None
        try:
            registered, opponent = await _start_pair(server)
            await _close_clients(registered, opponent)

            with pytest.raises(
                AuthenticationRejectedError,
                match="invalid_credentials",
            ):
                await _start_client(
                    server,
                    register=False,
                    password="definitely the wrong password",
                )
        finally:
            await _close_clients(
                registered if registered is not None and registered.is_connected else None,
                opponent if opponent is not None and opponent.is_connected else None,
            )
            await server.close()

    asyncio.run(scenario())


def test_network_client_reports_matchmaking_timeout(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            match_timeout_seconds=0.01,
        )
        await server.start()
        try:
            with pytest.raises(MatchmakingTimeoutError, match="match_timeout"):
                await _start_client(server)
        finally:
            await server.close()

    asyncio.run(scenario())


def test_network_client_recovers_to_lobby_after_interactive_match_timeout(
    auth_service,
):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            match_timeout_seconds=0.01,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        client = None
        try:
            client = await _authenticate_client(server, "Alice")
            client.start_matchmaking()
            await _wait_for_client_state(client, ConnectionState.LOBBY)

            assert client.lobby_error == "match_timeout"
            assert client.failure is None

            client.create_room()
            deadline = asyncio.get_running_loop().time() + 2.0
            while client.room_code != "AB12":
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("room was not created after timeout")
                await asyncio.sleep(0.01)
            client.cancel_room()
            await _wait_for_client_state(client, ConnectionState.LOBBY)
        finally:
            await _close_clients(client)
            await server.close()

    asyncio.run(scenario())


def test_network_client_rejects_invalid_match_timeout():
    with pytest.raises(ValueError, match="INVALID_MATCH_TIMEOUT"):
        NetworkClient(
            "ws://localhost:1",
            "Alice",
            PASSWORD,
            match_timeout=0,
        )


def test_network_client_reconnects_same_session_after_socket_drop(auth_service):
    async def scenario():
        registry = GameRegistry()
        server = GameServer(
            port=0,
            registry=registry,
            auth_service=auth_service,
            reconnect_grace_period_seconds=1.0,
        )
        await server.start()
        client = opponent = None
        try:
            client, opponent = await _start_pair(server)
            game_id = client.initial_state.game_id
            match = registry.get(game_id)
            original = next(
                context
                for context in match.connections()
                if context.session_token == client.session_token
            )
            original_connection_id = original.connection_id
            original_thread = client._transport._thread

            await original.websocket.close(code=1011, reason="test-drop")

            deadline = asyncio.get_running_loop().time() + 2.0
            restored = None
            while (
                restored is None
                or client.connection_status.state
                is not ConnectionState.CONNECTED
            ):
                restored = next(
                    (
                        context
                        for context in match.connections()
                        if (
                            context.session_token == client.session_token
                            and context.connection_id != original_connection_id
                        )
                    ),
                    None,
                )
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("client did not reconnect")
                await asyncio.sleep(0.01)

            assert client._transport._thread is original_thread
            assert client.connection_status.state is ConnectionState.CONNECTED
            assert restored.game_id == game_id
            assert restored.color.value == client.initial_state.assigned_color
            assert not match.is_paused

            second_connection_id = restored.connection_id
            await restored.websocket.close(code=1011, reason="second-test-drop")
            deadline = asyncio.get_running_loop().time() + 2.0
            restored_again = None
            while (
                restored_again is None
                or client.connection_status.state
                is not ConnectionState.CONNECTED
            ):
                restored_again = next(
                    (
                        context
                        for context in match.connections()
                        if (
                            context.session_token == client.session_token
                            and context.connection_id != second_connection_id
                        )
                    ),
                    None,
                )
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("client did not reconnect a second time")
                await asyncio.sleep(0.01)

            assert client._transport._thread is original_thread
            assert client.connection_status.state is ConnectionState.CONNECTED
            assert not match.is_paused
        finally:
            await _close_clients(client, opponent)
            await server.close()

    asyncio.run(scenario())


def test_network_client_reports_terminal_failure_after_grace_expires(
    auth_service,
):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            reconnect_grace_period_seconds=0.15,
        )
        await server.start()
        client = opponent = None
        try:
            client, opponent = await _start_pair(server)
            await server.close()

            deadline = asyncio.get_running_loop().time() + 2.0
            while client.connection_status.state is not ConnectionState.FAILED:
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("client did not report reconnect failure")
                await asyncio.sleep(0.01)

            assert not client.is_connected
            assert client.failure is not None
        finally:
            await _close_clients(client, opponent)
            await server.close()

    asyncio.run(scenario())
