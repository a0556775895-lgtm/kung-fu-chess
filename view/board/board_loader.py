import numpy as np

from ..img import Img
from ..image_utils import ensure_alpha
from .. import config


class BoardLoader:
    """Loads board.png once, sized to the current geometry (not a
    separate constant — so the board and geometry never 'drift' to
    different sizes). Composites it onto a wider canvas that leaves a
    HUD panel on each side (geometry.board_origin_x). Keeps a 'clean'
    copy (no pieces) for reuse every frame."""

    def __init__(self, geometry, image_path=config.BOARD_IMAGE_PATH):
        """Store geometry and image path; no board image is loaded yet."""
        self._geometry = geometry
        self._image_path = image_path
        self._clean_board = None
        # No call to load() here — construction is cheap, loading is explicit

    def load(self) -> None:
        """Load the board image sized to the current geometry, and cache
        it composited onto a full-canvas background with HUD panels."""
        board = Img()
        board.read(
            str(self._image_path),
            size=(self._geometry.window_width, self._geometry.window_height),
        )
        board.img = ensure_alpha(board.img)

        canvas = np.empty(
            (self._geometry.canvas_height, self._geometry.canvas_width, 4),
            dtype=board.img.dtype,
        )
        canvas[..., :3] = config.PANEL_BG_COLOR
        canvas[..., 3] = 255

        x0, y0 = self._geometry.board_origin_x, self._geometry.board_origin_y
        x1 = x0 + self._geometry.window_width
        y1 = y0 + self._geometry.window_height
        canvas[y0:y1, x0:x1] = board.img

        self._clean_board = canvas

    def reload(self) -> None:
        """Called only on a resize event — reloads at the current geometry size."""
        self.load()

    def fresh_canvas(self) -> Img:
        """Returns a new Img with a clean copy of the board — called at
        the start of every frame, before the renderers draw pieces on it."""
        canvas = Img()
        canvas.img = self._clean_board.copy()
        return canvas