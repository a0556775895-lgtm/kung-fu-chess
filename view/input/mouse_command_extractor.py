from model.position import Position
from .commands import ClickCommand, JumpCommand, Command


class MouseCommandExtractor:
    """Responsible only for the offset (board position within the window).
    All pixel->cell computation is delegated to the existing BoardMapper —
    not duplicated here."""

    def __init__(self, board_mapper, geometry):
        """Store the board mapper and geometry used to translate raw window pixels into board positions."""
        self._board_mapper = board_mapper
        self._geometry = geometry

    def _extract_position(self, raw_x: int, raw_y: int) -> Position | None:
        """Convert raw window pixel coordinates to a board Position, or None if outside the board."""
        board_x = raw_x - self._geometry.board_origin_x
        board_y = raw_y - self._geometry.board_origin_y

        position = self._board_mapper.pixel_to_position(board_x, board_y)
        if not self._board_mapper.is_inside_board(position):
            return None
        return position

    def extract_left_click(self, raw_x: int, raw_y: int) -> Command | None:
        """Convert a left click's raw pixel coordinates into a ClickCommand, or None if outside the board."""
        position = self._extract_position(raw_x, raw_y)
        return ClickCommand(position) if position is not None else None

    def extract_right_click(self, raw_x: int, raw_y: int) -> Command | None:
        """Convert a right click's raw pixel coordinates into a JumpCommand, or None if outside the board."""
        position = self._extract_position(raw_x, raw_y)
        return JumpCommand(position) if position is not None else None