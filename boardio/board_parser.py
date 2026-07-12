"""Parse text board input into a grid of Piece/None.

Extracted 1:1 from the old `Board._parse_board` — no logic change, only
relocation. `Board` no longer owns parsing; it just calls `parse_board`
and stores the result.
"""

from model.position import Position
from rules.piece_factory import PieceFactory


def parse_board(board_lines):
    """Parse `board_lines` (list of space-separated token strings) into
    a grid of Piece/None.

    Returns `(grid, rows, cols)`.
    Raises `ValueError("ROW_WIDTH_MISMATCH")` if rows have inconsistent
    widths — same error contract as the original code, so `main.py`'s
    existing error handling doesn't need to change.
    """

    grid = []
    first_row_width = None

    for row_index, row in enumerate(board_lines):
        tokens = row.split()

        if first_row_width is None:
            first_row_width = len(tokens)
        elif len(tokens) != first_row_width:
            raise ValueError("ROW_WIDTH_MISMATCH")

        current_row = []

        for col_index, token in enumerate(tokens):
            if token == ".":
                current_row.append(None)
            else:
                piece = PieceFactory.create_piece(
                    token, cell=Position(row_index, col_index)
                )
                current_row.append(piece)

        grid.append(current_row)

    rows = len(grid)
    cols = first_row_width

    return grid, rows, cols