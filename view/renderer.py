"""Text-mode rendering of game state.

Per Design Guide, section 12: the renderer receives GameSnapshot data
only -- never the live Board or Piece objects. This module rebuilds a
plain grid of piece tokens ("wP", "bK", ".", ...) from the snapshot's
`pieces` (a list of PieceSnapshot, each with a logical `cell` Position,
not pixels) and `board_width`/`board_height`, then hands that grid to
BoardPrinter, which owns the actual line-formatting/printing logic.
"""

from dataclasses import dataclass
from typing import List, Optional
from boardio.board_printer import print_board


@dataclass
class PieceSnapshot:
    kind: str
    color: str
    cell: object
    state: str


@dataclass
class GameSnapshot:
    board_width: int
    board_height: int
    pieces: List[PieceSnapshot]
    selected_cell: object
    game_over: bool


def render_snapshot(snapshot) -> None:
    """Print `snapshot` (a GameSnapshot) as a text board."""
    grid = [
        [None for _ in range(snapshot.board_width)]
        for _ in range(snapshot.board_height)
    ]

    for piece_snapshot in snapshot.pieces:
        cell = piece_snapshot.cell
        grid[cell.row][cell.col] = f"{piece_snapshot.color}{piece_snapshot.kind}"

    print_board(grid)