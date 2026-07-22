"""Immutable settings that define one authoritative match."""

from dataclasses import dataclass


GAME_CONFIG_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GameConfig:
    """Client-requested or server-approved logical game configuration."""

    schema_version: int
    board_rows: int
    board_cols: int
    opening: str
