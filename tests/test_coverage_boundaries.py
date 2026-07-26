"""Boundary and rejection tests that keep production coverage meaningful."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from boardio.board_parser import BoardParser
from boardio.board_factory import STANDARD_GAME_CONFIG
from bus.event_bus import EventBus
from client import cli_auth
from client import network_client as network_client_module
from client.network_client import NetworkClient
from client.network_event_adapter import NetworkEventAdapter
from client.remote_game_engine_proxy import RemoteGameEngineProxy
from client.snapshot_board_view import SnapshotBoardView
from engine.events import GameStarted
from engine.game_engine import GameEngine
from engine.snapshot import GameSnapshot, PieceSnapshot
from model.game_state import GameState
from model.piece import PieceColor
from model.position import Position
from networking.auth_protocol import (
    AuthProtocolError,
    AuthResponse,
    LoginRequest,
    encode_auth_ok,
    encode_login,
    parse_auth_response,
    validate_username,
)
from networking.game_config_serializer import (
    GameConfigSerializationError,
    GameConfigSerializer,
)
from networking.protocol import (
    ConfigResponse,
    JumpCommand,
    MoveCommand,
    ProtocolError,
    algebraic_to_position,
    decode_event,
    decode_state,
    encode_error,
    encode_event,
    encode_jump,
    encode_move,
    encode_config_accepted,
    encode_state,
    parse_client_command,
    parse_command_response,
    parse_config_response,
    parse_join,
    position_to_algebraic,
)
from networking.snapshot_serializer import (
    GameSnapshotSerializer,
    SnapshotSerializationError,
)
from server.dal.database import connect_database, init_schema
from server.dal.repository import UserRepository
from server.dal.unit_of_work import SqliteUnitOfWork
from server.game.admission import GameAdmission
from server.game.controller import GameController
from server.game.game_registry import GameRegistry
from server.game.game_result import FinishReason, GameResult
from server.game.match import Match
from server.game.tick_loop import advance_matches
from server.services.auth import AuthService, PasswordPolicy
from server.transport.connection import ConnectionContext, ConnectionRole
from server.transport.game_server import GameServer
from server.transport.connection_io import run_connection_io
from texttests.script_parser import ScriptParseError, parse_script


def _snapshot(**changes):
    base = GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[
            PieceSnapshot("white-pawn", "P", "w", Position(6, 4), "IDLE"),
        ],
        selected_cell=None,
        game_over=False,
        game_id="default",
        role="PLAYER",
        assigned_color="w",
        sequence=1,
    )
    return replace(base, **changes)


class _FakeNetwork:
    def __init__(self, initial_state):
        self.initial_state = initial_state
        self.sent = []
        self.incoming = []

    def send(self, message):
        self.sent.append(message)

    def drain_messages(self):
        messages, self.incoming = self.incoming, []
        return messages


def test_event_bus_absent_unsubscribe_is_safe():
    bus = EventBus()
    handler = lambda _event: None
    bus.unsubscribe(GameStarted, handler)
    bus.subscribe(GameStarted, lambda _event: None)
    bus.unsubscribe(GameStarted, handler)


def test_cli_uses_default_input_and_password_functions(monkeypatch):
    answers = iter(["login", "Alice"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(cli_auth.getpass, "getpass", lambda _prompt: "secret")

    credentials = cli_auth.prompt_credentials()

    assert credentials.username == "Alice"
    assert credentials.password == "secret"


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"type": "MOTION", "source": {}, "destination": {}, "piece": {}, "duration_ms": True}, "INVALID_EVENT_POSITION"),
        ({"type": "MOTION", "source": "a1", "destination": {}, "piece": {}, "duration_ms": 1}, "INVALID_EVENT_POSITION"),
        ({"type": "JUMP", "position": {"row": True, "col": 0}, "piece": {}}, "INVALID_EVENT_POSITION"),
        ({"type": "JUMP", "position": {"row": 0, "col": 0}, "piece": "pawn"}, "INVALID_EVENT_PIECE"),
        ({"type": "JUMP", "position": {"row": 0, "col": 0}, "piece": {"id": "", "kind": "P", "color": "w", "state": "IDLE"}}, "INVALID_EVENT_PIECE"),
        ({"type": "UNKNOWN"}, "UNKNOWN_EVENT_TYPE"),
    ],
)
def test_network_event_adapter_rejects_invalid_payloads(payload, reason):
    with pytest.raises(ProtocolError, match=reason):
        NetworkEventAdapter().publish(payload)


def test_network_event_adapter_rejects_non_integer_duration():
    payload = {
        "type": "MOTION",
        "source": {"row": 0, "col": 0},
        "destination": {"row": 0, "col": 1},
        "piece": {"id": "p", "kind": "P", "color": "w", "state": "MOVING"},
        "duration_ms": True,
    }
    with pytest.raises(ProtocolError, match="INVALID_EVENT_DURATION"):
        NetworkEventAdapter().publish(payload)


def test_network_event_adapter_exposes_its_local_bus():
    bus = EventBus()
    assert NetworkEventAdapter(bus).bus is bus


def test_remote_proxy_validates_handshake_and_messages():
    with pytest.raises(ValueError, match="PLAYER_COLOR_REQUIRED"):
        RemoteGameEngineProxy(_FakeNetwork(_snapshot(assigned_color=None)))
    with pytest.raises(ValueError, match="GAME_ID_REQUIRED"):
        RemoteGameEngineProxy(_FakeNetwork(_snapshot(game_id=None)))

    network = _FakeNetwork(_snapshot())
    proxy = RemoteGameEngineProxy(network)
    assert proxy.assigned_color == "w"
    assert proxy.request_move(Position(6, 4), Position(5, 4)).startswith("move-")

    network.incoming = ["unexpected"]
    with pytest.raises(ProtocolError, match="UNEXPECTED_SERVER_MESSAGE"):
        proxy.process_network_messages()

    network.incoming = [encode_event({
        "type": "GAME_STARTED",
        "game_id": "default",
        "sequence": True,
    })]
    with pytest.raises(ProtocolError, match="INVALID_SEQUENCE"):
        proxy.process_network_messages()


def test_snapshot_board_view_requires_snapshot():
    with pytest.raises(TypeError, match="SNAPSHOT_REQUIRED"):
        SnapshotBoardView("not-a-snapshot")


def test_game_state_rejects_invalid_winner():
    with pytest.raises(ValueError, match="INVALID_WINNER_COLOR"):
        GameState().end_game("w")


@pytest.mark.parametrize(
    "operation,reason",
    [
        (lambda: parse_auth_response(123), "MESSAGE_NOT_TEXT"),
        (lambda: validate_username(None), "INVALID_USERNAME"),
        (lambda: validate_username("__"), "INVALID_USERNAME"),
        (lambda: encode_login(LoginRequest("login-1", "Alice", None)), "INVALID_PASSWORD_VALUE"),
    ],
)
def test_auth_protocol_rejects_invalid_boundary_values(operation, reason):
    with pytest.raises(AuthProtocolError, match=reason):
        operation()


def test_game_config_serializer_rejects_wrong_types():
    with pytest.raises(GameConfigSerializationError, match="INVALID_GAME_CONFIG"):
        GameConfigSerializer.to_dict({})
    with pytest.raises(GameConfigSerializationError, match="GAME_CONFIG_NOT_OBJECT"):
        GameConfigSerializer.from_dict([])
    payload = GameConfigSerializer.to_dict(STANDARD_GAME_CONFIG)
    payload["schema_version"] = True
    with pytest.raises(GameConfigSerializationError, match="INVALID_GAME_CONFIG_VERSION"):
        GameConfigSerializer.from_dict(payload)


@pytest.mark.parametrize(
    "operation,reason",
    [
        (lambda: parse_join(None), "MESSAGE_NOT_TEXT"),
        (lambda: parse_config_response(None), "MESSAGE_NOT_TEXT"),
        (lambda: parse_config_response("CONFIG_ACCEPTED id {"), "INVALID_GAME_CONFIG_JSON"),
        (lambda: parse_client_command(None), "MESSAGE_NOT_TEXT"),
        (lambda: encode_move(MoveCommand("m", "X", "P", Position(0, 0), Position(0, 1))), "INVALID_MOVE"),
        (lambda: encode_jump(JumpCommand("j", "X", "P", Position(0, 0))), "INVALID_JUMP"),
        (lambda: encode_error("id", "two words"), "INVALID_ERROR_REASON"),
        (lambda: parse_command_response("WHAT id"), "MALFORMED_RESPONSE"),
        (lambda: decode_state("OTHER {}"), "NOT_STATE_MESSAGE"),
        (lambda: encode_event([]), "INVALID_EVENT"),
        (lambda: decode_event("OTHER {}"), "NOT_EVENT_MESSAGE"),
        (lambda: decode_event("EVENT {"), "INVALID_EVENT_JSON"),
        (lambda: decode_event("EVENT []"), "INVALID_EVENT"),
        (lambda: algebraic_to_position("z9"), "INVALID_SQUARE"),
        (lambda: position_to_algebraic("a1"), "INVALID_POSITION"),
    ],
)
def test_game_protocol_rejects_invalid_boundary_values(operation, reason):
    with pytest.raises(ProtocolError, match=reason):
        operation()


def test_config_response_rejects_malformed_envelope():
    with pytest.raises(ProtocolError, match="MALFORMED_CONFIG_RESPONSE"):
        parse_config_response("CONFIG_ACCEPTED")


def test_snapshot_serializer_rejects_invalid_nested_values():
    valid = GameSnapshotSerializer.to_dict(_snapshot())
    cases = [
        ("INVALID_POSITION", {"selected_cell": "a1"}),
        ("INVALID_SNAPSHOT_PAYLOAD", {"pieces": ["pawn"]}),
        ("MISSING_CELL", {"pieces": [{"id": "p", "kind": "P", "color": "w", "state": "IDLE", "cell": None}]}),
        ("INVALID_BOARD", {"board": []}),
        ("INVALID_PIECES", {"pieces": {}}),
        ("INVALID_ID", {"pieces": [{"id": "", "kind": "P", "color": "w", "state": "IDLE", "cell": {"row": 0, "col": 0}}]}),
        ("INVALID_WINNER_COLOR", {"winner_color": 1}),
        ("INVALID_SERVER_TIME_MS", {"server_time_ms": True}),
        ("INVALID_GAME_OVER", {"game_over": 1}),
        ("INVALID_SCORES", {"scores": {"w": True}}),
        ("INVALID_PLAYER_NAMES", {"player_names": {"w": ""}}),
    ]
    for reason, changes in cases:
        payload = dict(valid)
        payload.update(changes)
        with pytest.raises(SnapshotSerializationError, match=reason):
            GameSnapshotSerializer.from_dict(payload)


def test_repository_rejects_invalid_username_and_binary_fields():
    connection = connect_database(":memory:")
    try:
        init_schema(connection)
        repository = UserRepository(connection)
        with pytest.raises(ValueError, match="INVALID_USERNAME"):
            repository.get_by_username("")
        with pytest.raises(ValueError, match="INVALID_PASSWORD_HASH"):
            repository.create_user("Alice", "", b"salt")
        with pytest.raises(ValueError, match="INVALID_SALT"):
            repository.create_user("Alice", b"hash", b"")
        with pytest.raises(Exception) as exc_info:
            repository.create_user("Alice", b"hash", b"salt", rating=-1)
        assert type(exc_info.value).__name__ == "IntegrityError"
    finally:
        connection.close()


def test_unit_of_work_rejects_reentry_and_reuse_after_close():
    connection = connect_database(":memory:")
    init_schema(connection)
    unit = SqliteUnitOfWork(connection, close_connection=True)
    with unit:
        with pytest.raises(RuntimeError, match="UNIT_OF_WORK_ALREADY_ACTIVE"):
            unit.__enter__()
    with pytest.raises(RuntimeError, match="UNIT_OF_WORK_CLOSED"):
        unit.__enter__()


def test_admission_release_ignores_already_removed_match():
    admission = GameAdmission(GameRegistry())
    context = ConnectionContext("c", "missing", ConnectionRole.PLAYER)
    admission.release(context)


def test_registry_and_controller_report_missing_game():
    registry = GameRegistry()
    with pytest.raises(KeyError, match="GAME_NOT_FOUND"):
        registry.remove("missing")
    context = ConnectionContext("c", "missing", ConnectionRole.PLAYER, PieceColor.WHITE)
    response = GameController(registry).handle_message(context, "JUMP jump-1 WPa2")
    assert parse_command_response(response).reason == "game_not_found"


def test_controller_rejects_unassigned_color_and_opponent_piece():
    engine = GameEngine(BoardParser.parse(["wK bK"]))
    match = Match("game", engine)
    registry = GameRegistry()
    registry.add(match)
    context = ConnectionContext("c", "game", ConnectionRole.PLAYER, None)
    match.add_connection(context)

    response = GameController(registry).handle_message(context, "JUMP j-1 WKa8")
    assert parse_command_response(response).reason == "color_not_assigned"

    context.color = PieceColor.WHITE
    response = GameController(registry).handle_message(context, "JUMP j-2 WKb8")
    assert parse_command_response(response).reason == "wrong_color"


def test_game_result_and_match_validate_lifecycle_inputs():
    with pytest.raises(ValueError, match="INVALID_WINNER_COLOR"):
        GameResult("w", FinishReason.KING_CAPTURE, 1000)
    with pytest.raises(ValueError, match="INVALID_FINISH_REASON"):
        GameResult(PieceColor.WHITE, "KING_CAPTURE", 1000)

    with pytest.raises(ValueError, match="INVALID_GAME_ID"):
        Match("", SimpleNamespace(bus=EventBus()))


def test_match_validates_connections_result_and_close():
    engine = GameEngine(BoardParser.parse(["wK bK"]))
    match = Match("game", engine)
    context = ConnectionContext("c", "game", ConnectionRole.PLAYER, PieceColor.WHITE)
    match.add_connection(context)
    with pytest.raises(ValueError, match="CONNECTION_ALREADY_EXISTS"):
        match.add_connection(context)
    outsider = ConnectionContext("other", "game", ConnectionRole.PLAYER)
    with pytest.raises(ValueError, match="CONNECTION_NOT_REGISTERED"):
        match.snapshot_for(outsider)
    with pytest.raises(ValueError, match="INVALID_GAME_RESULT"):
        match.finish(None)

    match.close()
    assert match.connections() == ()


def test_match_rejects_engine_game_over_without_winner():
    class BrokenEngine:
        def __init__(self):
            self.bus = EventBus()
            self.game_over = True
            self.winner_color = None

        def wait(self, _milliseconds):
            pass

        def snapshot(self):
            return _snapshot(server_time_ms=0)

    with pytest.raises(RuntimeError, match="GAME_OVER_WITHOUT_WINNER"):
        Match("broken", BrokenEngine()).advance_time(1)


def test_tick_loop_zero_elapsed_time_is_a_noop():
    advance_matches(GameRegistry(), 0, 50)


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"iterations": 0}, "INVALID_PBKDF2_ITERATIONS"),
        ({"unit_of_work_factory": None}, "UNIT_OF_WORK_FACTORY_NOT_CALLABLE"),
        ({"salt_factory": None}, "SALT_FACTORY_NOT_CALLABLE"),
        ({"password_policy": PasswordPolicy(minimum_characters=0)}, "INVALID_MINIMUM_PASSWORD_LENGTH"),
        ({"password_policy": PasswordPolicy(maximum_bytes=0)}, "INVALID_MAXIMUM_PASSWORD_BYTES"),
    ],
)
def test_auth_service_validates_configuration(kwargs, reason):
    defaults = {
        "unit_of_work_factory": lambda: None,
        "iterations": 1,
        "salt_factory": lambda _size: b"x" * 16,
    }
    defaults.update(kwargs)
    with pytest.raises((TypeError, ValueError), match=reason):
        AuthService(**defaults)


def test_auth_service_rejects_invalid_generated_salt():
    with pytest.raises(ValueError, match="INVALID_GENERATED_SALT"):
        AuthService(
            lambda: None,
            iterations=1,
            salt_factory=lambda _size: b"short",
        )


def test_connection_rejects_non_text_message():
    context = ConnectionContext("c", "g", ConnectionRole.PLAYER)
    with pytest.raises(TypeError, match="OUTBOUND_MESSAGE_NOT_TEXT"):
        context.enqueue(b"bytes")


def test_game_server_requires_auth_and_reports_inactive_state():
    with pytest.raises(TypeError, match="AUTH_SERVICE_REQUIRED"):
        GameServer()

    server = GameServer(auth_service=object())
    with pytest.raises(RuntimeError, match="server_not_running"):
        _ = server.bound_port
    with pytest.raises(RuntimeError, match="server_not_running"):
        asyncio.run(server.serve_forever())
    asyncio.run(server.close())


def test_game_server_serve_forever_delegates_to_listener():
    class StopServing(Exception):
        pass

    class FakeServer:
        sockets = [object()]

        async def serve_forever(self):
            raise StopServing

    server = GameServer(auth_service=object())
    server._server = FakeServer()
    with pytest.raises(StopServing):
        asyncio.run(server.serve_forever())


def test_connection_io_propagates_reader_failure():
    class BrokenWebSocket:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("reader_failed")

        async def send(self, _message):
            pass

    context = ConnectionContext(
        "c",
        "g",
        ConnectionRole.PLAYER,
        websocket=BrokenWebSocket(),
    )
    with pytest.raises(RuntimeError, match="reader_failed"):
        asyncio.run(run_connection_io(context, SimpleNamespace()))


@pytest.mark.parametrize(
    "kwargs,reason,error_type",
    [
        ({"uri": ""}, "INVALID_SERVER_URI", ValueError),
        ({"password": None}, "PASSWORD_NOT_TEXT", TypeError),
        ({"register": "yes"}, "REGISTER_FLAG_NOT_BOOLEAN", TypeError),
        ({"connect_timeout": 0}, "INVALID_CONNECT_TIMEOUT", ValueError),
        ({"queue_size": 0}, "INVALID_QUEUE_SIZE", ValueError),
    ],
)
def test_network_client_validates_constructor(kwargs, reason, error_type):
    values = {
        "uri": "ws://localhost:1",
        "username": "Alice",
        "password": "secret",
    }
    values.update(kwargs)
    with pytest.raises(error_type, match=reason):
        NetworkClient(**values)


def test_network_client_unavailable_state_and_invalid_timeouts():
    client = NetworkClient("ws://localhost:1", "Alice", "secret")
    for property_name in ("auth_response", "config_response", "initial_state"):
        with pytest.raises(RuntimeError, match="client_not_started"):
            getattr(client, property_name)
    with pytest.raises(RuntimeError, match="client_not_authenticated"):
        _ = client.session_token
    with pytest.raises(ValueError, match="INVALID_START_TIMEOUT"):
        client.start(timeout=0)
    with pytest.raises(ValueError, match="INVALID_CLOSE_TIMEOUT"):
        client.close(timeout=0)
    client.close()


def test_network_client_rejects_repeated_start_without_starting_thread():
    client = NetworkClient("ws://localhost:1", "Alice", "secret")
    client._thread = object()
    with pytest.raises(RuntimeError, match="client_already_started"):
        client.start()


def test_network_client_send_validates_type_and_capacity():
    client = NetworkClient(
        "ws://localhost:1",
        "Alice",
        "secret",
        queue_size=1,
    )
    client._connected = True
    with pytest.raises(TypeError, match="OUTGOING_MESSAGE_NOT_TEXT"):
        client.send(b"bytes")
    client.send("first")
    with pytest.raises(RuntimeError, match="client_outgoing_queue_full"):
        client.send("second")


def test_network_client_close_reports_stuck_thread():
    class StuckThread:
        def join(self, _timeout=None):
            pass

        def is_alive(self):
            return True

    client = NetworkClient("ws://localhost:1", "Alice", "secret")
    client._thread = StuckThread()
    with pytest.raises(TimeoutError, match="client_close_timeout"):
        client.close(timeout=0.01)


def test_network_client_start_timeout_and_generic_failure(monkeypatch):
    class FakeThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def join(self, _timeout=None):
            pass

        def is_alive(self):
            return False

    monkeypatch.setattr(network_client_module, "Thread", FakeThread)
    timed_out = NetworkClient("ws://localhost:1", "Alice", "secret")
    with pytest.raises(TimeoutError, match="client_start_timeout"):
        timed_out.start(timeout=0.01)

    failed = NetworkClient("ws://localhost:1", "Alice", "secret")
    failed._failure = ValueError("background failed")
    failed._ready.set()
    with pytest.raises(ConnectionError, match="client_connection_failed"):
        failed.start()


def test_network_client_queue_stop_discards_oldest_message():
    client = NetworkClient(
        "ws://localhost:1",
        "Alice",
        "secret",
        queue_size=1,
    )
    client._outgoing.put_nowait("pending")
    client._queue_stop_signal()
    assert client._outgoing.get_nowait() is network_client_module._STOP


def test_network_client_reader_rejects_binary_and_full_queue():
    class Messages:
        def __init__(self, values):
            self._values = iter(values)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._values)
            except StopIteration:
                raise StopAsyncIteration

    binary_client = NetworkClient("ws://localhost:1", "Alice", "secret")
    with pytest.raises(TypeError, match="INCOMING_MESSAGE_NOT_TEXT"):
        asyncio.run(binary_client._reader_loop(Messages([b"bytes"])))

    full_client = NetworkClient(
        "ws://localhost:1",
        "Alice",
        "secret",
        queue_size=1,
    )
    with pytest.raises(RuntimeError, match="client_incoming_queue_full"):
        asyncio.run(full_client._reader_loop(Messages(["first", "second"])))


class _FakeClientWebSocket:
    def __init__(self, received, incoming=()):
        self._received = iter(received)
        self._incoming = iter(incoming)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, _type, _value, _traceback):
        return False

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        return next(self._received)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._incoming)
        except StopIteration:
            await asyncio.Future()


@pytest.mark.parametrize(
    "response,reason",
    [
        ("ERR another-request invalid_credentials", "auth_request_id_mismatch"),
        (
            encode_auth_ok(
                AuthResponse(
                    "another-request",
                    1,
                    "Alice",
                    1200,
                    "session-token",
                )
            ),
            "auth_request_id_mismatch",
        ),
    ],
)
def test_network_client_rejects_mismatched_auth_request_id(
    monkeypatch,
    response,
    reason,
):
    websocket = _FakeClientWebSocket([response])
    monkeypatch.setattr(network_client_module, "connect", lambda *_args, **_kwargs: websocket)
    monkeypatch.setattr(
        network_client_module.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="fixed"),
    )
    client = NetworkClient("ws://localhost:1", "Alice", "secret")

    with pytest.raises(ConnectionError, match=reason):
        asyncio.run(client._run_connection())


def test_network_client_propagates_reader_task_failure(monkeypatch):
    auth = encode_auth_ok(
        AuthResponse("login-fixed", 1, "Alice", 1200, "session-token")
    )
    config = encode_config_accepted("join-fixed", STANDARD_GAME_CONFIG)
    state = encode_state(_snapshot())
    websocket = _FakeClientWebSocket(
        [auth, config, state],
        incoming=[b"binary-message"],
    )
    monkeypatch.setattr(network_client_module, "connect", lambda *_args, **_kwargs: websocket)
    monkeypatch.setattr(
        network_client_module.uuid,
        "uuid4",
        lambda: SimpleNamespace(hex="fixed"),
    )
    client = NetworkClient("ws://localhost:1", "Alice", "secret")

    with pytest.raises(TypeError, match="INCOMING_MESSAGE_NOT_TEXT"):
        asyncio.run(client._run_connection())


def test_script_parser_rejects_missing_sections_and_unknown_commands():
    with pytest.raises(ScriptParseError, match="MISSING_BOARD_SECTION"):
        parse_script("Commands:\nprint board")
    assert parse_script("Board:\nwK").commands == []
    with pytest.raises(ScriptParseError, match="UNKNOWN_COMMAND"):
        parse_script("Board:\nwK\nCommands:\ndance")
