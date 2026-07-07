from abc import ABC, abstractmethod


class Piece(ABC):
    """Base class for all chess pieces."""

    def __init__(self, color: str, symbol: str, move_time: int):
        self._color = color
        self._symbol = symbol
        self._move_time = move_time

    @property
    def color(self):
        return self._color

    def get_move_time(self):
        return self._move_time

    def __str__(self):
        return f"{self._color}{self._symbol}"

    @abstractmethod
    def is_valid_move(self, source_row, source_col, destination_row, destination_col):
        """Returns True if the move is legal for this piece."""
        pass