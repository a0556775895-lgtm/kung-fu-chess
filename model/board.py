# רשת הלוח הלוגית — מיקום כלים, בדיקת גבולות וביצוע הזזה בפועל.
from model.position import Position


class Board:
    """The logical board grid: stores piece placement and exposes
    atomic operations (place, remove, move). Knows nothing about
    movement rules, timing, or rendering.
    """

    def __init__(self, grid, rows, cols):
        """Store the piece grid and its dimensions."""
        self._grid = grid
        self.rows = rows
        self.cols = cols

    def get_grid(self):
        """Return the board grid."""
        return self._grid

    def is_inside_board(self, position: Position) -> bool:
        """Return whether a position is inside the board."""
        return (
            0 <= position.row < self.rows
            and 0 <= position.col < self.cols
        )

    def get_piece_at(self, position: Position):
        """Return the piece at the given position, or None."""
        if not self.is_inside_board(position):
            raise ValueError(f"Position {position} is outside the board.")
        return self._grid[position.row][position.col]

    def place_piece(self, position: Position, piece):
        """Place a piece on the board."""
        if self._grid[position.row][position.col] is not None:
            raise ValueError(f"Cell {position} is already occupied.")
        self._grid[position.row][position.col] = piece

    def remove_piece(self, position: Position):
        """Remove the piece from a board cell."""
        self._grid[position.row][position.col] = None

    def move_piece(self, source: Position, destination: Position):
        """Move a piece from source to destination.

        Returns the captured piece (or None if the destination was empty),
        so the caller (RealTimeArbiter) can update its state and check
        for king capture.
        """
        piece = self.get_piece_at(source)
        if piece is None:
            raise ValueError(f"No piece at {source}.")

        self.remove_piece(source)

        captured = self.get_piece_at(destination)
        if captured is not None:
            self.remove_piece(destination)

        self.place_piece(destination, piece)
        piece.cell = destination
        return captured
