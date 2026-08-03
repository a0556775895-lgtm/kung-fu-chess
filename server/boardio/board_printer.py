# הדפסת מצב הלוח הלוגי ל-stdout.
"""Print a board grid to stdout."""


def print_board(grid):
    """Print grid (list of rows of Piece/None): pieces as 'wP'/'bK', empty cells as '.'."""
    for row in grid:
        print(" ".join(str(piece) if piece else "." for piece in row))