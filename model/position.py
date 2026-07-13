from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """Immutable (row, col) coordinate on the board."""

    row: int
    col: int