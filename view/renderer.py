# רנדור טקסטואלי של מצב המשחק מתוך GameSnapshot.
"""Text rendering from GameSnapshot — never from live Board or Piece objects."""

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