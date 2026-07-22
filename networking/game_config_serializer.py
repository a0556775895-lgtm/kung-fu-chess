"""Versioned JSON serialization for GameConfig."""

import json
from typing import Any

from model.game_config import GAME_CONFIG_SCHEMA_VERSION, GameConfig


_FIELDS = {"schema_version", "board_rows", "board_cols", "opening"}


class GameConfigSerializationError(ValueError):
    """Raised when a game-config payload is malformed or unsupported."""


class GameConfigSerializer:
    """Convert GameConfig values to and from their shared wire format."""

    @staticmethod
    def to_dict(config: GameConfig) -> dict[str, Any]:
        """Convert a GameConfig to a JSON-compatible dictionary."""
        if not isinstance(config, GameConfig):
            raise GameConfigSerializationError("INVALID_GAME_CONFIG")
        return {
            "schema_version": config.schema_version,
            "board_rows": config.board_rows,
            "board_cols": config.board_cols,
            "opening": config.opening,
        }

    @classmethod
    def to_json(cls, config: GameConfig) -> str:
        """Encode a GameConfig as compact deterministic JSON."""
        return json.dumps(
            cls.to_dict(config),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> GameConfig:
        """Validate a decoded payload and reconstruct GameConfig."""
        if not isinstance(payload, dict):
            raise GameConfigSerializationError("GAME_CONFIG_NOT_OBJECT")
        if set(payload) != _FIELDS:
            raise GameConfigSerializationError("INVALID_GAME_CONFIG_FIELDS")
        if type(payload["schema_version"]) is not int:
            raise GameConfigSerializationError("INVALID_GAME_CONFIG_VERSION")
        if payload["schema_version"] != GAME_CONFIG_SCHEMA_VERSION:
            raise GameConfigSerializationError("UNSUPPORTED_GAME_CONFIG_VERSION")
        if type(payload["board_rows"]) is not int or type(payload["board_cols"]) is not int:
            raise GameConfigSerializationError("INVALID_BOARD_SIZE_TYPE")
        if not isinstance(payload["opening"], str) or not payload["opening"]:
            raise GameConfigSerializationError("INVALID_OPENING")
        return GameConfig(
            schema_version=payload["schema_version"],
            board_rows=payload["board_rows"],
            board_cols=payload["board_cols"],
            opening=payload["opening"],
        )

    @classmethod
    def from_json(cls, payload: str) -> GameConfig:
        """Decode JSON and reject malformed game-config payloads."""
        try:
            decoded = json.loads(payload)
        except (json.JSONDecodeError, TypeError) as exc:
            raise GameConfigSerializationError("INVALID_GAME_CONFIG_JSON") from exc
        return cls.from_dict(decoded)
