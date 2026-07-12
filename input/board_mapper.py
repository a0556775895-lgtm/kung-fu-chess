"""Pixel <-> board-cell translation.

Replaces `board_geometry.py` (`ARCHITECTURE_PLAN.md`, section 3: same
role, new name/location). The one real change beyond relocation: this
version speaks `Position` instead of raw `(row, col)` ints, matching the
rest of the new layers (`model/position.py`, `rules/rule_engine.py`) —
callers no longer have to build a `Position` themselves right after
calling this.
"""

from model.position import Position


class BoardMapper:
    """Translate pixel coordinates to board cells and check bounds."""

    def __init__(self, rows, cols, cell_size=100):
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size

    def update_dimensions(self, rows, cols):
        self.rows = rows
        self.cols = cols

    def pixel_to_position(self, x, y) -> Position:
        """Convert pixel coordinates to a board `Position`.

        Ported 1:1 from the old `BoardGeometry.pixel_to_cell` (same
        `y // cell_size, x // cell_size` math) — only the return type
        changed, from a `(row, col)` tuple to a `Position`.
        """
        row = y // self.cell_size
        col = x // self.cell_size
        return Position(row, col)

    def is_inside_board(self, position: Position) -> bool:
        return 0 <= position.row < self.rows and 0 <= position.col < self.cols