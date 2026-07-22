"""Map approved GameConfig presets to fresh board instances."""

from boardio.standard_opening import create_standard_board
from model.board import Board
from model.game_config import GAME_CONFIG_SCHEMA_VERSION, GameConfig


STANDARD_GAME_CONFIG = GameConfig(
    schema_version=GAME_CONFIG_SCHEMA_VERSION,
    board_rows=8,
    board_cols=8,
    opening="standard",
)


def is_supported_game_config(config: GameConfig) -> bool:
    """Whether the server currently has a real board preset for config."""
    return config == STANDARD_GAME_CONFIG


def create_board(config: GameConfig) -> Board:
    """Create a fresh board for a supported config, rejecting unknown presets."""
    if not is_supported_game_config(config):
        raise ValueError("UNSUPPORTED_GAME_CONFIG")
    return create_standard_board()
