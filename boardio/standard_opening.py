"""Create fresh boards in the standard chess opening position."""

from boardio.board_parser import BoardParser
from model.board import Board


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


def create_standard_board() -> Board:
    """Return an independent board initialized to the standard opening."""
    return BoardParser.parse(STANDARD_OPENING)
