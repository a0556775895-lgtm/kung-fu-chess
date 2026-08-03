"""In-memory integration tests across server routing, matches and broadcasting."""

import asyncio

import pytest

from server.boardio.board_parser import BoardParser
from server.engine.game_engine import GameEngine
from networking.models.piece import PieceColor
from networking.models.position import Position
from networking.protocols.game import (
    decode_event,
    decode_state,
    parse_command_response,
)
from server.game.controller import GameController
from server.game.game_result import FinishReason, GameResult
from server.game.game_registry import GameRegistry
from server.game.match import Match
from server.transport.connection import ConnectionContext, ConnectionRole


def make_engine():
    """Build a minimal legal board used independently by each test Match."""
    return GameEngine(BoardParser.parse([
        ".  .  .  .  bK .  .  .",
        ".  .  .  .  .  .  .  .",
        ".  .  .  .  .  .  .  .",
        ".  .  .  .  .  .  .  .",
        ".  .  .  .  .  .  .  .",
        ".  .  .  .  .  .  .  .",
        ".  .  .  .  .  .  .  .",
        "wR .  .  .  wK .  .  .",
    ]))


def make_context(
    connection_id,
    game_id,
    color=PieceColor.WHITE,
    role=ConnectionRole.PLAYER,
    maxsize=256,
    user_id=None,
    username=None,
    session_token=None,
):
    """Build a connection with a configurable bounded queue for backpressure tests."""
    return ConnectionContext(
        connection_id=connection_id,
        game_id=game_id,
        role=role,
        color=color,
        user_id=user_id,
        username=username,
        session_token=session_token,
        outbound=asyncio.Queue(maxsize=maxsize),
    )


def setup_match(game_id="game-1"):
    """Wire a registry, isolated Match and one authorized white connection."""
    registry = GameRegistry()
    match = Match(game_id, make_engine())
    registry.add(match)
    context = make_context("conn-1", game_id)
    match.add_connection(context)
    return registry, match, context


def drain(context):
    """Read all currently queued messages without starting an async writer."""
    messages = []
    while not context.outbound.empty():
        messages.append(context.outbound.get_nowait())
    return messages


class _RecordingActivityLogger:
    def __init__(self):
        self.entries = []
        self.closed = False

    def record(self, event_type, **fields):
        if not self.closed:
            self.entries.append((event_type, fields))

    def close(self):
        self.closed = True


def test_registry_add_get_remove_and_duplicate_protection():
    registry, match, _ = setup_match()
    assert registry.get("game-1") is match
    assert "game-1" in registry
    assert len(registry) == 1
    with pytest.raises(ValueError, match="GAME_ALREADY_EXISTS"):
        registry.add(match)
    assert registry.remove("game-1") is match
    with pytest.raises(KeyError, match="GAME_NOT_FOUND"):
        registry.get("game-1")


def test_broadcaster_isolates_events_between_matches():
    first = Match("first", make_engine())
    second = Match("second", make_engine())
    first_context = make_context("c1", "first")
    second_context = make_context("c2", "second")
    first.add_connection(first_context)
    second.add_connection(second_context)

    first.engine.start_game()

    event = decode_event(first_context.outbound.get_nowait())
    assert event["type"] == "GAME_STARTED"
    assert event["game_id"] == "first"
    assert second_context.outbound.empty()


def test_controller_accepts_authorized_move_and_broadcasts_state():
    registry, match, context = setup_match()
    response = GameController(registry).handle_message(context, "MOVE req-1 WRa1a2")

    assert parse_command_response(response).accepted is True
    messages = drain(context)
    assert decode_event(messages[0])["type"] == "MOTION"
    state = decode_state(messages[1])
    assert state.game_id == "game-1"
    assert state.assigned_color == "w"
    assert state.role == "PLAYER"
    assert len(state.active_motions) == 1
    assert state.active_motions[0].source.row == 7
    assert state.active_motions[0].destination.row == 6


def test_match_activity_log_records_lifecycle_commands_and_game_over():
    activity = _RecordingActivityLogger()
    registry = GameRegistry()
    match = Match("logged-game", make_engine(), activity_logger=activity)
    registry.add(match)
    context = make_context(
        "logged-connection",
        "logged-game",
        user_id=7,
        username="Alice",
    )
    match.add_connection(context)

    accepted = GameController(registry).handle_message(
        context,
        "MOVE move-logged WRa1a2",
    )
    context.role = ConnectionRole.SPECTATOR
    rejected = GameController(registry).handle_message(
        context,
        "JUMP jump-rejected WRa1",
    )
    match.finish(
        GameResult(PieceColor.WHITE, FinishReason.RESIGN, 25)
    )
    match.close()

    event_types = [event_type for event_type, _fields in activity.entries]
    assert parse_command_response(accepted).accepted
    assert parse_command_response(rejected).reason == "spectator_forbidden"
    assert {
        "connection_joined",
        "motion",
        "command_accepted",
        "command_rejected",
        "game_finished",
        "game_over",
    } <= set(event_types)
    command_entry = next(
        fields
        for event_type, fields in activity.entries
        if event_type == "command_accepted"
    )
    assert command_entry["request_id"] == "move-logged"
    assert command_entry["user_id"] == 7
    assert activity.closed


def test_controller_accepts_jump_and_returns_correlated_response():
    registry, _, context = setup_match()
    response = GameController(registry).handle_message(context, "JUMP jump-1 WRa1")

    parsed = parse_command_response(response)
    assert parsed.accepted is True
    assert parsed.request_id == "jump-1"
    messages = drain(context)
    assert decode_event(messages[0])["type"] == "JUMP"
    assert decode_state(messages[1]).airborne_until


@pytest.mark.parametrize(
    "context_kwargs,message,reason",
    [
        ({"color": PieceColor.BLACK}, "MOVE req-2 WRa1a2", "wrong_color"),
        ({"role": ConnectionRole.SPECTATOR, "color": None}, "MOVE req-3 WRa1a2", "spectator_forbidden"),
        ({}, "MOVE req-4 WQa1a2", "piece_mismatch"),
        ({}, "MOVE req-5 WRb1b2", "empty_source"),
    ],
)
def test_controller_rejects_unauthorized_or_false_piece_claims(context_kwargs, message, reason):
    registry, match, context = setup_match()
    for key, value in context_kwargs.items():
        setattr(context, key, value)
    response = parse_command_response(GameController(registry).handle_message(context, message))
    assert response.accepted is False
    assert response.reason == reason


def test_controller_rejects_unregistered_connection():
    registry, _, _ = setup_match()
    impostor = make_context("impostor", "game-1")
    response = parse_command_response(
        GameController(registry).handle_message(impostor, "MOVE req-6 WRa1a2")
    )
    assert response.reason == "connection_not_registered"


def test_match_snapshot_is_personalized_per_connection():
    _, match, white = setup_match()
    spectator = make_context("spectator", "game-1", color=None, role=ConnectionRole.SPECTATOR)
    match.add_connection(spectator)
    match.send_state(spectator)
    snapshot = decode_state(spectator.outbound.get_nowait())
    assert snapshot.role == "SPECTATOR"
    assert snapshot.assigned_color is None
    assert snapshot.sequence == 1


def test_match_retains_player_seat_and_name_without_live_connection():
    match = Match("game-1", make_engine())
    original = make_context(
        "original",
        "game-1",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
        session_token="alice-token",
    )
    match.add_connection(original)

    assert match.remove_connection("original") is original
    assert match.connections() == ()
    assert match.player_user_ids == {PieceColor.WHITE: 1}
    assert match.player_usernames == {PieceColor.WHITE: "Alice"}

    restored = make_context(
        "restored",
        "game-1",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
        session_token="alice-token",
    )
    match.add_connection(restored)
    match.send_state(restored)

    snapshot = decode_state(restored.outbound.get_nowait())
    assert snapshot.player_names == {"w": "Alice", "b": "Black"}


def test_match_prevents_reserved_seat_takeover_and_duplicate_live_color():
    match = Match("game-1", make_engine())
    alice = make_context(
        "alice",
        "game-1",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
    )
    duplicate_alice = make_context(
        "duplicate-alice",
        "game-1",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
    )
    bob = make_context(
        "bob",
        "game-1",
        color=PieceColor.WHITE,
        user_id=2,
        username="Bob",
    )
    match.add_connection(alice)

    with pytest.raises(ValueError, match="PLAYER_SEAT_ALREADY_CONNECTED"):
        match.add_connection(duplicate_alice)

    match.remove_connection("alice")
    with pytest.raises(ValueError, match="PLAYER_SEAT_ALREADY_ASSIGNED"):
        match.add_connection(bob)

    assert match.player_user_ids == {PieceColor.WHITE: 1}
    assert match.player_usernames == {PieceColor.WHITE: "Alice"}


def test_disconnected_player_seats_remain_isolated_between_matches():
    first = Match("first", make_engine())
    second = Match("second", make_engine())
    first_alice = make_context(
        "alice",
        "first",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
    )
    second_bob = make_context(
        "bob",
        "second",
        color=PieceColor.WHITE,
        user_id=2,
        username="Bob",
    )
    first.add_connection(first_alice)
    second.add_connection(second_bob)

    first.remove_connection("alice")
    second.remove_connection("bob")

    assert first.player_usernames == {PieceColor.WHITE: "Alice"}
    assert second.player_usernames == {PieceColor.WHITE: "Bob"}


def test_match_close_releases_persistent_player_seats():
    match = Match("game-1", make_engine())
    context = make_context(
        "alice",
        "game-1",
        color=PieceColor.WHITE,
        user_id=1,
        username="Alice",
    )
    match.add_connection(context)

    match.close()

    assert match.connections() == ()
    assert match.player_user_ids == {}
    assert match.player_usernames == {}


def test_slow_connection_does_not_block_and_records_drop():
    context = make_context("slow", "game-1", maxsize=1)
    context.enqueue("old")
    context.enqueue("new")
    assert context.outbound.get_nowait() == "new"
    assert context.dropped_messages == 1


def test_match_rejects_connection_from_another_game():
    match = Match("first", make_engine())
    with pytest.raises(ValueError, match="CONNECTION_GAME_MISMATCH"):
        match.add_connection(make_context("c", "second"))


def test_match_advances_authoritative_time_and_rejects_negative_tick():
    _, match, context = setup_match()
    match.advance_time(125)
    match.send_state(context)
    snapshot = decode_state(context.outbound.get_nowait())
    assert snapshot.server_time_ms == 125
    with pytest.raises(ValueError, match="NEGATIVE_TICK"):
        match.advance_time(-1)


def test_match_pause_freezes_time_and_rejects_commands_until_all_return():
    registry, match, white = setup_match()
    black = make_context(
        "black",
        "game-1",
        color=PieceColor.BLACK,
        user_id=2,
    )
    match.add_connection(black)
    match.advance_time(100)

    assert match.pause_for(PieceColor.BLACK)
    assert not match.pause_for(PieceColor.WHITE)
    assert match.disconnected_colors == {
        PieceColor.WHITE,
        PieceColor.BLACK,
    }
    match.advance_time(5_000)
    assert match.server_time_ms() == 100

    response = parse_command_response(
        GameController(registry).handle_message(white, "MOVE paused WRa1a2")
    )
    assert response.reason == "game_paused"

    assert not match.resume_for(PieceColor.BLACK)
    assert match.is_paused
    assert match.resume_for(PieceColor.WHITE)
    assert not match.is_paused
    match.advance_time(50)
    assert match.server_time_ms() == 150


def test_match_pause_validates_color_and_does_not_pause_finished_game():
    _, match, _ = setup_match()
    with pytest.raises(ValueError, match="INVALID_PLAYER_COLOR"):
        match.pause_for("w")
    with pytest.raises(ValueError, match="INVALID_PLAYER_COLOR"):
        match.resume_for("w")

    match.finish(GameResult(
        winner_color=PieceColor.WHITE,
        reason=FinishReason.RESIGN,
        duration_ms=0,
    ))
    assert not match.pause_for(PieceColor.BLACK)
    assert not match.is_paused


def test_arrival_event_uses_authoritative_engine_time():
    registry, match, context = setup_match()
    GameController(registry).handle_message(context, "MOVE timed WRa1a2")
    drain(context)

    match.advance_time(1000)

    arrival = decode_event(context.outbound.get_nowait())
    assert arrival["type"] == "ARRIVAL"
    assert arrival["server_time_ms"] == 1000


def test_match_records_king_capture_result_and_snapshot_winner():
    engine = GameEngine(BoardParser.parse(["wR bK"]))
    match = Match("result-game", engine)

    assert engine.request_move(Position(0, 0), Position(0, 1)).is_accepted
    match.advance_time(1000)

    assert match.result == GameResult(
        winner_color=PieceColor.WHITE,
        reason=FinishReason.KING_CAPTURE,
        duration_ms=1000,
    )
    assert engine.snapshot().winner_color == "w"


def test_match_finish_is_idempotent():
    match = Match("result-game", make_engine())
    first = GameResult(
        winner_color=PieceColor.WHITE,
        reason=FinishReason.RESIGN,
        duration_ms=1000,
    )
    second = GameResult(
        winner_color=PieceColor.BLACK,
        reason=FinishReason.DISCONNECT,
        duration_ms=2000,
    )

    assert match.finish(first) is True
    assert match.finish(second) is False
    assert match.result is first


def test_match_persists_authenticated_players_once_on_finish():
    class CompletionRecorder:
        def __init__(self):
            self.calls = []

        def complete(self, **arguments):
            self.calls.append(arguments)

    completion = CompletionRecorder()
    match = Match(
        "result-game",
        make_engine(),
        match_instance_id="instance-1",
        completion_service=completion,
    )
    white = make_context(
        "white",
        "result-game",
        color=PieceColor.WHITE,
        user_id=10,
    )
    black = make_context(
        "black",
        "result-game",
        color=PieceColor.BLACK,
        user_id=20,
    )
    match.add_connection(white)
    match.add_connection(black)
    match.remove_connection(white.connection_id)
    result = GameResult(
        winner_color=PieceColor.BLACK,
        reason=FinishReason.RESIGN,
        duration_ms=300_000,
    )

    assert match.finish(result) is True
    assert match.finish(result) is False
    assert match.player_user_ids == {
        PieceColor.WHITE: 10,
        PieceColor.BLACK: 20,
    }
    assert completion.calls == [{
        "match_instance_id": "instance-1",
        "white_user_id": 10,
        "black_user_id": 20,
        "result": result,
    }]
    assert white.outbound.empty()
    final_state = decode_state(black.outbound.get_nowait())
    assert final_state.game_over
    assert final_state.winner_color == "b"
    assert decode_event(black.outbound.get_nowait())["type"] == "GAME_OVER"
    assert black.outbound.empty()


def test_match_requires_both_authenticated_players_before_persistence():
    completion = type(
        "CompletionRecorder",
        (),
        {"complete": lambda self, **arguments: None},
    )()
    match = Match(
        "result-game",
        make_engine(),
        completion_service=completion,
    )
    match.add_connection(make_context(
        "white",
        "result-game",
        user_id=10,
    ))
    result = GameResult(
        winner_color=PieceColor.WHITE,
        reason=FinishReason.RESIGN,
        duration_ms=0,
    )

    with pytest.raises(RuntimeError, match="AUTHENTICATED_PLAYERS_REQUIRED"):
        match.finish(result)

    assert match.result is None


def test_match_does_not_notify_clients_when_persistence_fails():
    class FailingCompletion:
        def complete(self, **_arguments):
            raise RuntimeError("database_failed")

    engine = GameEngine(BoardParser.parse(["wR bK"]))
    match = Match(
        "result-game",
        engine,
        completion_service=FailingCompletion(),
    )
    white = make_context(
        "white",
        "result-game",
        color=PieceColor.WHITE,
        user_id=10,
    )
    black = make_context(
        "black",
        "result-game",
        color=PieceColor.BLACK,
        user_id=20,
    )
    match.add_connection(white)
    match.add_connection(black)

    assert engine.request_move(Position(0, 0), Position(0, 1)).is_accepted
    drain(white)
    drain(black)

    with pytest.raises(RuntimeError, match="database_failed"):
        match.advance_time(1000)

    assert match.result is None
    assert all(
        decode_event(message)["type"] != "GAME_OVER"
        for message in drain(white) + drain(black)
    )


@pytest.mark.parametrize("match_instance_id", ["", 123])
def test_match_validates_persistence_identity(match_instance_id):
    with pytest.raises(ValueError, match="INVALID_MATCH_INSTANCE_ID"):
        Match(
            "result-game",
            make_engine(),
            match_instance_id=match_instance_id,
        )


@pytest.mark.parametrize("duration_ms", [True, -1, 1.5])
def test_game_result_requires_non_negative_integer_duration(duration_ms):
    with pytest.raises(ValueError, match="INVALID_GAME_DURATION"):
        GameResult(PieceColor.WHITE, FinishReason.KING_CAPTURE, duration_ms)
