from dataclasses import dataclass
from model.position import Position
from . import config


@dataclass
class BoardGeometry:
    window_width: int = config.WINDOW_SIZE[0]
    window_height: int = config.WINDOW_SIZE[1]
    board_origin_x: int = 0
    board_origin_y: int = 0

    @property
    def rows(self) -> int:
        """Number of board rows."""
        return config.BOARD_ROWS

    @property
    def cols(self) -> int:
        """Number of board columns."""
        return config.BOARD_COLS

    @property
    def cell_w(self) -> int:
        """Pixel width of a single board cell, derived from the current window width."""
        return self.window_width // self.cols

    @property
    def cell_h(self) -> int:
        """Pixel height of a single board cell, derived from the current window height."""
        return self.window_height // self.rows

    def cell_to_pixel(self, position: Position) -> tuple[int, int]:
        """Convert a board Position to its top-left pixel coordinate on screen."""
        x = self.board_origin_x + position.col * self.cell_w
        y = self.board_origin_y + position.row * self.cell_h
        return x, y

    def resize(self, width: int, height: int) -> None:
        """Update the tracked window dimensions (e.g. after a window resize)."""
        self.window_width = width
        self.window_height = height