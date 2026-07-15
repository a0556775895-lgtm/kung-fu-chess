# תרגום פיקסלים לתא לוחי ובדיקת גבולות.
"""Pixel-to-cell translation and bounds checking."""

from model.position import Position


class BoardMapper:

    """Translate pixel coordinates to board cells and check bounds."""

    def __init__(self, rows, cols, cell_size=100):
        """Store board dimensions and pixel size of a cell."""
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size

    def update_dimensions(self, rows, cols):
        """Update the tracked board dimensions (e.g. after a window resize)."""
        self.rows = rows
        self.cols = cols

    def pixel_to_position(self, x, y) -> Position:
        """Convert pixel coordinates to a board `Position`.

        Ported 1:1 from the old `BoardGeometry.pixel_tocell` (same
        `y // cell_size, x // cell_size` math) — only the return type
        changed, from a `(row, col)` tuple to a `Position`.
        """
        row = y // self.cell_size
        col = x // self.cell_size
        return Position(row, col)

    def is_inside_board(self, position: Position) -> bool:
        """Return whether position falls within the board's row/col bounds."""
        return 0 <= position.row < self.rows and 0 <= position.col < self.cols