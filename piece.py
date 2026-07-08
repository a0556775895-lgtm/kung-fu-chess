from abc import ABC, abstractmethod
from enum import Enum, auto


class PieceColor(Enum):
    WHITE = "w"
    BLACK = "b"

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, PieceColor):
            return self is other
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self):
        return hash(self.value)


class PieceState(Enum):
    IDLE = auto()
    MOVING = auto()
    COOLDOWN = auto()
    JUMPING = auto()
    CAPTURED = auto()


class Piece(ABC):
    """Base class for all chess pieces."""

    def __init__(self, color, symbol: str, move_time: int, jump_duration: int = 1000):
        if isinstance(color, str):
            color = PieceColor(color)

        self._color = color
        self._symbol = symbol
        self._move_time = move_time
        self._jump_duration = jump_duration
        self._board = None
        self._state = PieceState.IDLE
        self._jump_finish_time = None

    @property
    def color(self):
        return self._color

    @property
    def move_time(self):
        return self._move_time

    def get_path_cells(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
    ):
        """Return intermediate cells between source and destination.

        Returns a list of (row, col) tuples representing intermediate
        cells between source and destination. Default: empty list.
        """

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
        """Return the `Board` instance this piece belongs to."""

        return self._board
    
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state: PieceState):
        """Set the piece state to a `PieceState` value."""

        self._state = new_state

    def start_jump(self, current_time):
        """Start a jump: set state to `JUMPING` and schedule finish time.

        `current_time` is the current time in milliseconds.
        """

        self._state = PieceState.JUMPING
        self._jump_finish_time = current_time + self._jump_duration

    def finish_jump(self):
        """Finish an ongoing jump and reset state/time."""

        self._state = PieceState.IDLE
        self._jump_finish_time = None

    def is_airborne(self):
        """Return True if the piece is currently in JUMPING state."""

        return self._state == PieceState.JUMPING
    
    def should_finish_jump(self, current_time):
        """Return True when a jump should finish based on `current_time`."""

        return (
            self._state == PieceState.JUMPING
            and current_time >= self._jump_finish_time
        )
    
    def is_royal(self):
        """Return True if capturing this piece ends the game. Default: False."""
        return False