"""The standard game configuration shared by clients and the server."""

from networking.models.game_config import GAME_CONFIG_SCHEMA_VERSION, GameConfig


STANDARD_GAME_CONFIG = GameConfig(
    schema_version=GAME_CONFIG_SCHEMA_VERSION,
    board_rows=8,
    board_cols=8,
    opening="standard",
)
