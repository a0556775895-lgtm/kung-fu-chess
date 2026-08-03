class BoardRenderer:
    """Draws the board image loaded by BoardLoader at its position on
    canvas. Must run before any other renderer, so pieces/highlight/HUD
    text land on top of it rather than under it."""

    def __init__(self, board_loader, geometry):
        """Store the board loader (image) and geometry (position) used for drawing."""
        self._board_loader = board_loader
        self._geometry = geometry

    def render(self, canvas, snapshot) -> None:
        """Draw the loaded board image at geometry.board_origin_x/y."""
        x, y = self._geometry.board_origin_x, self._geometry.board_origin_y
        self._board_loader.image.draw_on(canvas, x, y)
