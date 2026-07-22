"""Unit tests for the shared text protocol and its request correlation."""

import pytest

from engine.snapshot import GameSnapshot, PieceSnapshot
from model.game_config import GameConfig
from model.position import Position
from networking.protocol import (
    JumpCommand,
    JoinRequest,
    MoveCommand,
    ProtocolError,
    decode_event,
    decode_state,
    encode_config_accepted,
    encode_config_overridden,
    encode_error,
    encode_event,
    encode_jump,
    encode_join,
    encode_move,
    encode_ok,
    encode_state,
    parse_client_command,
    parse_command_response,
    parse_config_response,
    parse_join,
)


def test_move_command_round_trip():
    command = MoveCommand("req-1", "W", "Q", Position(6, 4), Position(3, 4))
    encoded = encode_move(command)
    assert encoded == "MOVE req-1 WQe2e5"
    assert parse_client_command(encoded) == command


def test_jump_command_round_trip():
    command = JumpCommand("req-2", "B", "N", Position(4, 4))
    encoded = encode_jump(command)
    assert encoded == "JUMP req-2 BNe4"
    assert parse_client_command(encoded) == command


@pytest.mark.parametrize(
    "message,reason",
    [
        ("", "MALFORMED_COMMAND"),
        ("MOVE no-token", "MALFORMED_COMMAND"),
        ("MOVE bad/id WQe2e5", "INVALID_REQUEST_ID"),
        ("MOVE req WQe9e5", "MALFORMED_MOVE"),
        ("JUMP req WQe2e4", "MALFORMED_JUMP"),
        ("CASTLE req WKe1g1", "UNKNOWN_COMMAND"),
    ],
)
def test_rejects_malformed_commands(message, reason):
    with pytest.raises(ProtocolError, match=reason):
        parse_client_command(message)


def test_command_responses_round_trip():
    assert parse_command_response(encode_ok("42")).accepted is True
    rejected = parse_command_response(encode_error("43", "resting"))
    assert rejected.accepted is False
    assert rejected.request_id == "43"
    assert rejected.reason == "resting"


def test_state_envelope_round_trip():
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[PieceSnapshot("p1", "Q", "w", Position(6, 4), "IDLE")],
        selected_cell=None,
        game_over=False,
    )
    assert decode_state(encode_state(snapshot)) == snapshot


def test_event_envelope_round_trip():
    payload = {"type": "GAMEOVER", "game_id": "default", "sequence": 9}
    assert decode_event(encode_event(payload)) == payload


def test_join_round_trip():
    config = GameConfig(1, 8, 8, "standard")
    request = JoinRequest("join-1", config)

    assert parse_join(encode_join(request)) == request


def test_config_accepted_round_trip():
    config = GameConfig(1, 8, 8, "standard")

    response = parse_config_response(encode_config_accepted("join-1", config))

    assert response.request_id == "join-1"
    assert response.was_overridden is False
    assert response.effective_config == config


def test_config_overridden_round_trip():
    effective = GameConfig(1, 8, 8, "standard")

    response = parse_config_response(encode_config_overridden("join-2", effective))

    assert response.was_overridden is True
    assert response.effective_config == effective


@pytest.mark.parametrize(
    "message,reason",
    [
        ("MOVE join-1 {}", "MALFORMED_JOIN"),
        ("JOIN bad/id {}", "INVALID_REQUEST_ID"),
        ("JOIN join-1 not-json", "INVALID_GAME_CONFIG_JSON"),
        ("JOIN join-1 {}", "INVALID_GAME_CONFIG_FIELDS"),
    ],
)
def test_rejects_malformed_join(message, reason):
    with pytest.raises(ProtocolError, match=reason):
        parse_join(message)
