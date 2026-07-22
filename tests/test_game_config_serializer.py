"""Tests for versioned, structurally validated game configuration."""

import pytest

from model.game_config import GameConfig
from networking.game_config_serializer import (
    GameConfigSerializationError,
    GameConfigSerializer,
)


def test_game_config_json_round_trip():
    config = GameConfig(1, 8, 8, "standard")

    assert GameConfigSerializer.from_json(GameConfigSerializer.to_json(config)) == config


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({}, "INVALID_GAME_CONFIG_FIELDS"),
        (
            {"schema_version": 2, "board_rows": 8, "board_cols": 8, "opening": "standard"},
            "UNSUPPORTED_GAME_CONFIG_VERSION",
        ),
        (
            {"schema_version": 1, "board_rows": "8", "board_cols": 8, "opening": "standard"},
            "INVALID_BOARD_SIZE_TYPE",
        ),
        (
            {"schema_version": 1, "board_rows": 8, "board_cols": 8, "opening": ""},
            "INVALID_OPENING",
        ),
    ],
)
def test_game_config_rejects_invalid_structure(payload, reason):
    with pytest.raises(GameConfigSerializationError, match=reason):
        GameConfigSerializer.from_dict(payload)
