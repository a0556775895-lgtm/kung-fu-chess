import asyncio

import pytest

from boardio.board_parser import BoardParser
from engine.game_engine import GameEngine
from model.piece import PieceColor
from server.connection import ConnectionContext, ConnectionRole
from server.controller import GameController
from server.game_registry import GameRegistry
from server.match import Match
from server.protocol import decode_event, decode_state, parse_command_response


def make_engine():
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


def make_context(connection_id, game_id, color=PieceColor.WHITE, role=ConnectionRole.PLAYER, maxsize=256):
    return ConnectionContext(
        connection_id=connection_id,
        game_id=game_id,
        role=role,
        color=color,
        outbound=asyncio.Queue(maxsize=maxsize),
    )


def setup_match(game_id="game-1"):
    registry = GameRegistry()
    match = Match(game_id, make_engine())
    registry.add(match)
    context = make_context("conn-1", game_id)
    match.add_connection(context)
    return registry, match, context


def drain(context):
    messages = []
    while not context.outbound.empty():
        messages.append(context.outbound.get_nowait())
    return messages


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


def test_arrival_event_uses_authoritative_engine_time():
    registry, match, context = setup_match()
    GameController(registry).handle_message(context, "MOVE timed WRa1a2")
    drain(context)

    match.advance_time(1000)

    arrival = decode_event(context.outbound.get_nowait())
    assert arrival["type"] == "ARRIVAL"
    assert arrival["server_time_ms"] == 1000
