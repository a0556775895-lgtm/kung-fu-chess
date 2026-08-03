"""Map approved GameConfig presets to fresh board instances."""

from networking.models.standard_game_config import STANDARD_GAME_CONFIG
from server.models.board import Board
from networking.models.game_config import GameConfig
from server.boardio.board_parser import BoardParser


STANDARD_OPENING = (
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
)


def is_supported_game_config(config: GameConfig) -> bool:
    """Whether the server currently has a real board preset for config."""
    return config == STANDARD_GAME_CONFIG


def create_board(config: GameConfig) -> Board:
    """Create a fresh board for a supported config, rejecting unknown presets."""
    if not is_supported_game_config(config):
        raise ValueError("UNSUPPORTED_GAME_CONFIG")
    return BoardParser.parse(STANDARD_OPENING)
