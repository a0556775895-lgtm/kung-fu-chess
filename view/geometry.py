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
        return config.BOARD_ROWS

    @property
    def cols(self) -> int:
        return config.BOARD_COLS

    @property
    def cell_w(self) -> int:
        return self.window_width // self.cols

    @property
    def cell_h(self) -> int:
        return self.window_height // self.rows

    def cell_to_pixel(self, position: Position) -> tuple[int, int]:
        x = self.board_origin_x + position.col * self.cell_w
        y = self.board_origin_y + position.row * self.cell_h
        return x, y

    def resize(self, width: int, height: int) -> None:
        self.window_width = width
        self.window_height = height