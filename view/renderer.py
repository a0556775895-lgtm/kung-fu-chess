"""Text rendering from GameSnapshot — never from live Board or Piece objects."""

from boardio.board_printer import print_board
from engine.snapshot import GameSnapshot, PieceSnapshot


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
