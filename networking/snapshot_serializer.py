"""Versioned JSON serialization for GameSnapshot."""

import json
from typing import Any

from engine.snapshot import GameSnapshot, MotionSnapshot, PieceSnapshot
from model.position import Position


SCHEMA_VERSION = 1


class SnapshotSerializationError(ValueError):
    """Raised when a snapshot payload is malformed or unsupported."""


class GameSnapshotSerializer:
    """The single wire-format boundary for complete game snapshots."""

    @staticmethod
    def to_dict(snapshot: GameSnapshot) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "board": {
                "width": snapshot.board_width,
                "height": snapshot.board_height,
            },
            "pieces": [
                {
                    "id": piece.id,
                    "kind": piece.kind,
                    "color": piece.color,
                    "cell": _position_to_dict(piece.cell),
                    "state": piece.state,
                }
                for piece in snapshot.pieces
            ],
            "selected_cell": _position_to_dict(snapshot.selected_cell),
            "game_over": snapshot.game_over,
            "active_motions": [
                {
                    "piece_id": motion.piece_id,
                    "source": _position_to_dict(motion.source),
                    "destination": _position_to_dict(motion.destination),
                    "start_time_ms": motion.start_time_ms,
                    "arrival_time_ms": motion.arrival_time_ms,
                }
                for motion in snapshot.active_motions
            ],
            "airborne_until": dict(snapshot.airborne_until),
            "resting_until": dict(snapshot.resting_until),
            "scores": dict(snapshot.scores),
            "winner_color": snapshot.winner_color,
            "server_time_ms": snapshot.server_time_ms,
            "game_id": snapshot.game_id,
            "role": snapshot.role,
            "assigned_color": snapshot.assigned_color,
            "sequence": snapshot.sequence,
        }

    @classmethod
    def to_json(cls, snapshot: GameSnapshot) -> str:
        return json.dumps(
            cls.to_dict(snapshot),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> GameSnapshot:
        try:
            if not isinstance(payload, dict):
                raise SnapshotSerializationError("SNAPSHOT_NOT_OBJECT")
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise SnapshotSerializationError("UNSUPPORTED_SNAPSHOT_VERSION")

            board = _required_dict(payload, "board")
            pieces_payload = _required_list(payload, "pieces")
            motions_payload = _required_list(payload, "active_motions")

            pieces = [
                PieceSnapshot(
                    id=_required_str(item, "id"),
                    kind=_required_str(item, "kind"),
                    color=_required_str(item, "color"),
                    cell=_required_position(item, "cell"),
                    state=_required_str(item, "state"),
                )
                for item in pieces_payload
            ]
            motions = [
                MotionSnapshot(
                    piece_id=_required_str(item, "piece_id"),
                    source=_required_position(item, "source"),
                    destination=_required_position(item, "destination"),
                    start_time_ms=_required_int(item, "start_time_ms"),
                    arrival_time_ms=_required_int(item, "arrival_time_ms"),
                )
                for item in motions_payload
            ]

            return GameSnapshot(
                board_width=_required_int(board, "width"),
                board_height=_required_int(board, "height"),
                pieces=pieces,
                selected_cell=_position_from_dict(payload.get("selected_cell")),
                game_over=_required_bool(payload, "game_over"),
                active_motions=motions,
                airborne_until=_string_int_dict(payload, "airborne_until"),
                resting_until=_string_int_dict(payload, "resting_until"),
                scores=_string_int_dict(payload, "scores"),
                winner_color=_optional_str(payload, "winner_color"),
                server_time_ms=_required_int(payload, "server_time_ms"),
                game_id=_optional_str(payload, "game_id"),
                role=_optional_str(payload, "role"),
                assigned_color=_optional_str(payload, "assigned_color"),
                sequence=_required_int(payload, "sequence"),
            )
        except SnapshotSerializationError:
            raise
        except (KeyError, TypeError) as exc:
            raise SnapshotSerializationError("INVALID_SNAPSHOT_PAYLOAD") from exc

    @classmethod
    def from_json(cls, payload: str) -> GameSnapshot:
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SnapshotSerializationError("INVALID_SNAPSHOT_JSON") from exc
        return cls.from_dict(decoded)


def _position_to_dict(position: Position | None) -> dict[str, int] | None:
    if position is None:
        return None
    return {"row": position.row, "col": position.col}


def _position_from_dict(payload: Any) -> Position | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise SnapshotSerializationError("INVALID_POSITION")
    return Position(_required_int(payload, "row"), _required_int(payload, "col"))


def _required_position(payload: Any, key: str) -> Position:
    if not isinstance(payload, dict):
        raise SnapshotSerializationError("INVALID_SNAPSHOT_PAYLOAD")
    position = _position_from_dict(payload.get(key))
    if position is None:
        raise SnapshotSerializationError(f"MISSING_{key.upper()}")
    return position


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _required_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _required_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return value


def _string_int_dict(payload: dict[str, Any], key: str) -> dict[str, int]:
    value = _required_dict(payload, key)
    if any(
        not isinstance(item_key, str)
        or isinstance(item_value, bool)
        or not isinstance(item_value, int)
        for item_key, item_value in value.items()
    ):
        raise SnapshotSerializationError(f"INVALID_{key.upper()}")
    return dict(value)
