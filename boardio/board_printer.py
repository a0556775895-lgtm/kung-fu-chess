"""Print a board's grid to stdout.

Extracted 1:1 from the old `Board.print_board` — no logic change, only
relocation.
"""


def print_board(grid):
    """Print `grid` (list of rows of Piece/None) exactly like the
    original `Board.print_board` did: one line per row, pieces shown via
    `str(piece)` (e.g. 'wP'), empty cells shown as '.'.
    """
    for row in grid:
        print(" ".join(str(piece) if piece else "." for piece in row))