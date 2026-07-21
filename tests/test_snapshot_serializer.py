import json

import pytest

from engine.snapshot import GameSnapshot, MotionSnapshot, PieceSnapshot
from model.position import Position
from networking.snapshot_serializer import (
    GameSnapshotSerializer,
    SnapshotSerializationError,
)


def make_full_snapshot():
    return GameSnapshot(
        board_width=8,
        board_height=8,
        pieces=[
            PieceSnapshot("white_queen", "Q", "w", Position(6, 4), "MOVING"),
            PieceSnapshot("black_king", "K", "b", Position(0, 4), "IDLE"),
        ],
        selected_cell=Position(6, 4),
        game_over=False,
        active_motions=[
            MotionSnapshot("white_queen", Position(6, 4), Position(3, 4), 100, 3100)
        ],
        airborne_until={"black_king": 900},
        resting_until={"white_queen": 5100},
        scores={"w": 3, "b": 1},
        winner_color=None,
        server_time_ms=250,
        game_id="game-7",
        role="PLAYER",
        assigned_color="w",
        sequence=12,
    )


def test_full_snapshot_json_round_trip():
    snapshot = make_full_snapshot()
    assert GameSnapshotSerializer.from_json(GameSnapshotSerializer.to_json(snapshot)) == snapshot


def test_serialized_snapshot_contains_schema_version():
    payload = GameSnapshotSerializer.to_dict(make_full_snapshot())
    assert payload["schema_version"] == 1


def test_rejects_unknown_schema_version():
    payload = GameSnapshotSerializer.to_dict(make_full_snapshot())
    payload["schema_version"] = 99
    with pytest.raises(SnapshotSerializationError, match="UNSUPPORTED_SNAPSHOT_VERSION"):
        GameSnapshotSerializer.from_dict(payload)


def test_rejects_invalid_json():
    with pytest.raises(SnapshotSerializationError, match="INVALID_SNAPSHOT_JSON"):
        GameSnapshotSerializer.from_json("{not-json")


def test_rejects_missing_required_snapshot_field():
    payload = GameSnapshotSerializer.to_dict(make_full_snapshot())
    del payload["pieces"]
    with pytest.raises(SnapshotSerializationError, match="INVALID_PIECES"):
        GameSnapshotSerializer.from_dict(payload)


def test_json_payload_is_an_object():
    with pytest.raises(SnapshotSerializationError, match="SNAPSHOT_NOT_OBJECT"):
        GameSnapshotSerializer.from_json(json.dumps([]))
