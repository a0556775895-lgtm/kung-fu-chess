from abc import ABC, abstractmethod

class Piece(ABC):
    """Base class for all chess pieces."""

    def __init__(self, color: str, symbol: str, move_time: int):
        self._color = color
        self._symbol = symbol
        self._move_time = move_time
        self._board = None
        self._is_airborne = False
        self._jump_finish_time = None

    @property
    def color(self):
        return self._color

    def get_move_time(self):
        return self._move_time

    def get_path_cells(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
    ):
        return []

    def __str__(self):
        return f"{self._color}{self._symbol}"

    @abstractmethod
    def is_valid_move(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
        destination_piece,
    ):
        """Returns True if the move is legal for this piece."""
        pass  # pragma: no cover

    @property
    def symbol(self):
        return self._symbol
    
    def set_board(self, board):
        self._board = board

    def get_board(self):
        return self._board
    
    def start_jump(self, current_time):
        self._is_airborne = True
        self._jump_finish_time = current_time + 1000

    def finish_jump(self):
        self._is_airborne = False
        self._jump_finish_time = None

    def is_airborne(self):
        return self._is_airborne
    
    def should_finish_jump(self, current_time):
        return (
            self._is_airborne
            and current_time >= self._jump_finish_time
        )