"""Unit tests for the snapshot board facade and remote engine adapter."""

from dataclasses import replace

import pytest

from client.remote_game_engine_proxy import RemoteGameEngineProxy
from client.snapshot_board_view import SnapshotBoardView
from engine.snapshot import GameSnapshot, PieceSnapshot
from model.position import Position
from networking.protocol import (
    ProtocolError,
    encode_event,
    encode_state,
    parse_client_command,
)


class _FakeNetworkClient:
    def __init__(self, initial_state):
        self.initial_state = initial_state
        self.sent = []
        self.incoming = []

    def send(self, message):
        self.sent.append(message)

    def drain_messages(self):
        messages = self.incoming
        self.incoming = []
        return messages


def _snapshot(*, sequence=1, white_cell=Position(6, 4)):
    return GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[
            PieceSnapshot("white-pawn", "P", "w", white_cell, "IDLE"),
            PieceSnapshot("black-pawn", "P", "b", Position(1, 4), "IDLE"),
        ],
        selected_cell=None,
        game_over=False,
        game_id="default",
        role="PLAYER",
        assigned_color="w",
        sequence=sequence,
    )


def _predictable_ids():
    counters = {"move": 0, "jump": 0}

    def create(prefix):
        counters[prefix] += 1
        return f"{prefix}-{counters[prefix]}"

    return create


def test_snapshot_board_view_reads_and_replaces_snapshot():
    initial = _snapshot()
    board = SnapshotBoardView(initial)

    assert (board.rows, board.cols) == (8, 8)
    assert board.get_piece_at(Position(6, 4)).id == "white-pawn"
    assert board.get_piece_at(Position(4, 4)) is None

    updated = _snapshot(sequence=2, white_cell=Position(5, 4))
    board.update(updated)

    assert board.snapshot is updated
    assert board.get_piece_at(Position(6, 4)) is None
    assert board.get_piece_at(Position(5, 4)).id == "white-pawn"


def test_snapshot_board_view_rejects_two_pieces_on_one_cell():
    snapshot = _snapshot()
    duplicate = replace(
        snapshot,
        pieces=[snapshot.pieces[0], replace(snapshot.pieces[1], cell=Position(6, 4))],
    )

    with pytest.raises(ValueError, match="DUPLICATE_PIECE_CELL"):
        SnapshotBoardView(duplicate)


def test_proxy_translates_owned_move_and_jump_to_wire_commands():
    network = _FakeNetworkClient(_snapshot())
    proxy = RemoteGameEngineProxy(network, request_id_factory=_predictable_ids())

    move_id = proxy.request_move(Position(6, 4), Position(5, 4))
    jump_id = proxy.request_jump(Position(6, 4))

    move = parse_client_command(network.sent[0])
    jump = parse_client_command(network.sent[1])
    assert move_id == "move-1"
    assert (move.color, move.kind, move.source, move.destination) == (
        "W", "P", Position(6, 4), Position(5, 4)
    )
    assert jump_id == "jump-1"
    assert (jump.color, jump.kind, jump.source) == ("W", "P", Position(6, 4))


def test_proxy_does_not_send_empty_or_opponent_source():
    network = _FakeNetworkClient(_snapshot())
    proxy = RemoteGameEngineProxy(network)

    assert proxy.request_move(Position(4, 4), Position(3, 4)) is None
    assert proxy.request_jump(Position(1, 4)) is None
    assert network.sent == []


def test_proxy_applies_new_state_and_ignores_stale_state():
    initial = _snapshot(sequence=5)
    newest = _snapshot(sequence=7, white_cell=Position(5, 4))
    stale = _snapshot(sequence=6, white_cell=Position(4, 4))
    network = _FakeNetworkClient(initial)
    network.incoming = [encode_state(newest), encode_state(stale)]
    proxy = RemoteGameEngineProxy(network)

    assert proxy.process_network_messages() == 2
    assert proxy.board.get_piece_at(Position(5, 4)).id == "white-pawn"
    assert proxy.board.get_piece_at(Position(4, 4)) is None
    selected = proxy.snapshot(Position(5, 4))
    assert selected.selected_cell == Position(5, 4)
    assert proxy.board.snapshot.selected_cell is None


def test_proxy_correlates_responses_and_queues_ordered_events():
    network = _FakeNetworkClient(_snapshot(sequence=1))
    network.incoming = [
        "OK move-1",
        "ERR jump-1 resting",
        encode_event({
            "type": "ARRIVAL",
            "game_id": "default",
            "sequence": 2,
            "server_time_ms": 500,
        }),
    ]
    proxy = RemoteGameEngineProxy(network)

    proxy.process_network_messages()

    assert proxy.pop_response("move-1").accepted
    rejected = proxy.pop_response("jump-1")
    assert not rejected.accepted
    assert rejected.reason == "resting"
    assert proxy.pop_response("missing") is None
    assert [event["type"] for event in proxy.drain_events()] == ["ARRIVAL"]
    assert proxy.drain_events() == []


def test_proxy_rejects_message_for_another_game():
    network = _FakeNetworkClient(_snapshot(sequence=1))
    network.incoming = [
        encode_event({
            "type": "ARRIVAL",
            "game_id": "other-game",
            "sequence": 2,
            "server_time_ms": 500,
        })
    ]
    proxy = RemoteGameEngineProxy(network)

    with pytest.raises(ProtocolError, match="GAME_ID_MISMATCH"):
        proxy.process_network_messages()
