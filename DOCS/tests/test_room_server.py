"""Real-WebSocket integration tests for F2 room commands."""

import asyncio

from websockets.asyncio.client import connect

from networking.models.standard_game_config import STANDARD_GAME_CONFIG
from networking.models.game_config import GameConfig
from networking.protocols.auth import (
    AuthResponse,
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
from networking.protocols.room import (
    CancelRoomRequest,
    CreateRoomRequest,
    JoinRoomRequest,
    encode_cancel_room,
    encode_create_room,
    encode_join_room,
    parse_room_response,
)
from server.game.room import RoomStatus
from server.game.room_registry import RoomRegistry
from server.transport.game_server import GameServer


PASSWORD = "correct horse battery"


async def _register(websocket, username, request_id) -> AuthResponse:
    await websocket.send(
        encode_register(
            RegisterRequest(request_id, username, PASSWORD)
        )
    )
    return parse_auth_response(await websocket.recv())


async def _receive_admission(websocket):
    return (
        parse_config_response(await websocket.recv()),
        decode_state(await websocket.recv()),
    )


def test_room_server_creates_one_match_for_creator_and_joiner(auth_service):
    async def scenario():
        room_registry = RoomRegistry()
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_registry=room_registry,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as creator, connect(uri) as joiner:
                creator_auth = await _register(
                    creator,
                    "Alice",
                    "register-creator",
                )
                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-1",
                            creator_auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                created = parse_room_response(await creator.recv())

                joiner_auth = await _register(
                    joiner,
                    "Bob",
                    "register-joiner",
                )
                await joiner.send(
                    encode_join_room(
                        JoinRoomRequest(
                            "join-room-1",
                            joiner_auth.session_token,
                            created.room_code,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                joined = parse_room_response(await joiner.recv())
                creator_admission, joiner_admission = await asyncio.gather(
                    _receive_admission(creator),
                    _receive_admission(joiner),
                )

                assert created.kind == "ROOM_CREATED"
                assert joined.kind == "ROOM_JOINED"
                assert joined.room_code == created.room_code == "AB12"
                assert creator_admission[1].assigned_color == "w"
                assert joiner_admission[1].assigned_color == "b"
                assert (
                    creator_admission[1].game_id
                    == joiner_admission[1].game_id
                )
                room = room_registry.get("AB12")
                assert room.status is RoomStatus.ACTIVE
                assert room.match.game_id == creator_admission[1].game_id
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_adds_third_client_as_read_only_spectator(auth_service):
    async def scenario():
        room_registry = RoomRegistry()
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_registry=room_registry,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as creator, connect(uri) as joiner:
                creator_auth = await _register(
                    creator,
                    "Alice",
                    "register-creator",
                )
                await creator.send(encode_create_room(CreateRoomRequest(
                    "create-1",
                    creator_auth.session_token,
                    STANDARD_GAME_CONFIG,
                )))
                created = parse_room_response(await creator.recv())

                joiner_auth = await _register(
                    joiner,
                    "Bob",
                    "register-joiner",
                )
                await joiner.send(encode_join_room(JoinRoomRequest(
                    "join-player",
                    joiner_auth.session_token,
                    created.room_code,
                    STANDARD_GAME_CONFIG,
                )))
                await joiner.recv()
                await asyncio.gather(
                    _receive_admission(creator),
                    _receive_admission(joiner),
                )

                spectator = await connect(uri)
                spectator_auth = await _register(
                    spectator,
                    "Carol",
                    "register-spectator",
                )
                await spectator.send(encode_join_room(JoinRoomRequest(
                    "join-spectator",
                    spectator_auth.session_token,
                    created.room_code,
                    STANDARD_GAME_CONFIG,
                )))

                joined = parse_room_response(await spectator.recv())
                spectator_config, spectator_state = (
                    await _receive_admission(spectator)
                )
                room = room_registry.get(created.room_code)

                assert joined.kind == "ROOM_JOINED"
                assert spectator_config.effective_config == STANDARD_GAME_CONFIG
                assert spectator_state.role == "SPECTATOR"
                assert spectator_state.assigned_color is None
                assert len(room.match.connections()) == 3

                room.match.broadcast_state()
                assert decode_state(await spectator.recv()).role == "SPECTATOR"

                await spectator.send("MOVE spectator-move WPa2a3")
                while True:
                    message = await spectator.recv()
                    if message.startswith(("OK ", "ERR ")):
                        response = parse_command_response(message)
                        if response.request_id == "spectator-move":
                            break
                assert response.reason == "spectator_forbidden"

                await spectator.close()
                for _attempt in range(20):
                    if len(room.match.connections()) == 2:
                        break
                    await asyncio.sleep(0.01)
                assert len(room.match.connections()) == 2
                assert not room.match.is_paused
                assert room.match.result is None
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_cancel_returns_creator_to_reusable_lobby(auth_service):
    async def scenario():
        generated_codes = iter(("AB12", "CD34"))
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: next(generated_codes),
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as creator:
                auth = await _register(
                    creator,
                    "Alice",
                    "register-creator",
                )
                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-1",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                first = parse_room_response(await creator.recv())

                await creator.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-1",
                            auth.session_token,
                            first.room_code,
                        )
                    )
                )
                cancelled = parse_room_response(await creator.recv())

                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-2",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                second = parse_room_response(await creator.recv())

                assert cancelled.kind == "ROOM_CANCELLED"
                assert cancelled.room_code == first.room_code == "AB12"
                assert second.kind == "ROOM_CREATED"
                assert second.room_code == "CD34"

                await creator.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-2",
                            auth.session_token,
                            second.room_code,
                        )
                    )
                )
                assert parse_room_response(
                    await creator.recv()
                ).kind == "ROOM_CANCELLED"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_reports_room_errors_without_dropping_lobby(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as player:
                auth = await _register(
                    player,
                    "Alice",
                    "register-player",
                )
                await player.send(
                    encode_join_room(
                        JoinRoomRequest(
                            "join-missing",
                            auth.session_token,
                            "ZZ99",
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                missing = parse_command_response(await player.recv())

                await player.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-missing",
                            auth.session_token,
                            "ZZ99",
                        )
                    )
                )
                cancel_missing = parse_command_response(await player.recv())

                await player.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-after-errors",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                created = parse_room_response(await player.recv())

                assert missing.reason == "room_not_found"
                assert cancel_missing.reason == "room_not_found"
                assert created.kind == "ROOM_CREATED"

                await player.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-final",
                            auth.session_token,
                            created.room_code,
                        )
                    )
                )
                await player.recv()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_validates_lobby_and_waiting_room_messages(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as creator:
                auth = await _register(
                    creator,
                    "Alice",
                    "register-creator",
                )

                await creator.send("CREATE_ROOM")
                assert parse_command_response(
                    await creator.recv()
                ).reason == "malformed_create_room"

                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-wrong-token",
                            "wrong-token",
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                assert parse_command_response(
                    await creator.recv()
                ).reason == "invalid_session_token"

                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-unsupported",
                            auth.session_token,
                            GameConfig(1, 9, 9, "standard"),
                        )
                    )
                )
                assert parse_command_response(
                    await creator.recv()
                ).reason == "unsupported_game_config"

                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-valid",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                created = parse_room_response(await creator.recv())

                await creator.send("CREATE_ROOM")
                assert parse_command_response(
                    await creator.recv()
                ).reason == "malformed_create_room"

                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-while-waiting",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                assert parse_command_response(
                    await creator.recv()
                ).reason == "room_waiting"

                await creator.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-wrong-token",
                            "wrong-token",
                            created.room_code,
                        )
                    )
                )
                assert parse_command_response(
                    await creator.recv()
                ).reason == "invalid_session_token"

                await creator.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-wrong-room",
                            auth.session_token,
                            "ZZ99",
                        )
                    )
                )
                assert parse_command_response(
                    await creator.recv()
                ).reason == "room_not_found"

                await creator.send(
                    encode_cancel_room(
                        CancelRoomRequest(
                            "cancel-valid",
                            auth.session_token,
                            created.room_code,
                        )
                    )
                )
                assert parse_room_response(
                    await creator.recv()
                ).kind == "ROOM_CANCELLED"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_rejects_invalid_generated_room_code(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: "bad!",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as creator:
                auth = await _register(
                    creator,
                    "Alice",
                    "register-creator",
                )
                await creator.send(
                    encode_create_room(
                        CreateRoomRequest(
                            "create-invalid-code",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )

                assert parse_command_response(
                    await creator.recv()
                ).reason == "invalid_room_code"
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_removes_room_when_creator_disconnects(auth_service):
    async def scenario():
        registry = RoomRegistry()
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_registry=registry,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            creator = await connect(uri)
            auth = await _register(
                creator,
                "Alice",
                "register-creator",
            )
            await creator.send(
                encode_create_room(
                    CreateRoomRequest(
                        "create-1",
                        auth.session_token,
                        STANDARD_GAME_CONFIG,
                    )
                )
            )
            await creator.recv()

            await creator.close()
            for _attempt in range(20):
                if len(registry) == 0:
                    break
                await asyncio.sleep(0.01)

            assert len(registry) == 0
        finally:
            await server.close()

    asyncio.run(scenario())


def test_room_server_close_wakes_waiting_creator(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            room_code_factory=lambda: "AB12",
        )
        await server.start()
        uri = f"ws://127.0.0.1:{server.bound_port}"
        creator = await connect(uri)
        auth = await _register(
            creator,
            "Alice",
            "register-creator",
        )
        await creator.send(
            encode_create_room(
                CreateRoomRequest(
                    "create-1",
                    auth.session_token,
                    STANDARD_GAME_CONFIG,
                )
            )
        )
        await creator.recv()

        await server.close()
        await creator.wait_closed()

    asyncio.run(scenario())


def test_room_server_rejects_message_sent_while_matchmaking(auth_service):
    async def scenario():
        server = GameServer(
            port=0,
            auth_service=auth_service,
            match_timeout_seconds=1,
        )
        await server.start()
        try:
            uri = f"ws://127.0.0.1:{server.bound_port}"
            async with connect(uri) as player:
                auth = await _register(
                    player,
                    "Alice",
                    "register-player",
                )
                await player.send(
                    encode_join(
                        JoinRequest(
                            "join-queue",
                            auth.session_token,
                            STANDARD_GAME_CONFIG,
                        )
                    )
                )
                await player.send("EXTRA_MESSAGE")

                assert parse_command_response(
                    await player.recv()
                ).reason == "unexpected_lobby_message"
        finally:
            await server.close()

    asyncio.run(scenario())
