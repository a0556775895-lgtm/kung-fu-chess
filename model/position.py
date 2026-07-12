class Position:
    """Immutable (row, col) coordinate on the board.

    Replaces the raw `(row, col)` tuples used throughout the old codebase
    (e.g. `piece.get_path_cells`, `Board._pending_source`). Using a real
    type instead of a tuple makes call sites self-documenting and gives us
    a single place to add validation or helper methods later.
    """

    __slots__ = ("_row", "_col")

    def __init__(self, row: int, col: int):
        self._row = row
        self._col = col

    @property
    def row(self):
        return self._row

    @property
    def col(self):
        return self._col

    def as_tuple(self):
        """Return (row, col) — useful at the boundary with legacy/grid code."""
        return (self._row, self._col)

    def __eq__(self, other):
        if isinstance(other, Position):
            return self._row == other._row and self._col == other._col
        return NotImplemented

    def __hash__(self):
        return hash((self._row, self._col))

    def __repr__(self):
        return f"Position(row={self._row}, col={self._col})"

    def __iter__(self):
        # Allows `row, col = position` for easy migration from tuple call sites.
        yield self._row
        yield self._col