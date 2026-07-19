# טוען את הרקע ואת שני הפאנלים הצדדיים ומרכיב אותם לקנבס אחד — נפרד מהלוח עצמו.
import cv2

from ..img import Img
from ..image_utils import ensure_alpha
from .. import config


class BackgroundLoader:
    """Loads background.png and side_panel.png once, sized to the current
    geometry, and composites them into one full-canvas image:
    background.png fills the whole canvas, and side_panel.png is drawn
    into each HUD panel (mirrored on the right, so both panels' text
    plaque faces the board). Kept separate from BoardLoader -- the board
    itself is drawn as a Renderer on top of this canvas each frame, not
    baked into it."""

    def __init__(self, geometry,
                 background_image_path=config.BACKGROUND_IMAGE_PATH,
                 side_panel_image_path=config.SIDE_PANEL_IMAGE_PATH):
        """Store geometry and image paths; nothing is loaded yet."""
        self._geometry = geometry
        self._background_image_path = background_image_path
        self._side_panel_image_path = side_panel_image_path
        self._clean_canvas = None
        # No call to load() here — construction is cheap, loading is explicit

    def load(self) -> None:
        """Load the background and side-panel images sized to the current
        geometry, and cache them composited onto one full-canvas image."""
        background = Img()
        background.read(
            str(self._background_image_path),
            size=(self._geometry.canvas_width, self._geometry.canvas_height),
        )
        canvas = Img()
        canvas.img = ensure_alpha(background.img)

        panel_size = (config.SCORE_PANEL_WIDTH, self._geometry.canvas_height)

        left_panel = Img()
        left_panel.read(str(self._side_panel_image_path), size=panel_size, keep_aspect=True)
        left_panel.img = ensure_alpha(left_panel.img)
        left_panel.draw_on(canvas, 0, 0)

        right_panel = Img()
        right_panel.read(str(self._side_panel_image_path), size=panel_size, keep_aspect=True)
        right_panel.img = ensure_alpha(right_panel.img)
        right_panel.img = cv2.flip(right_panel.img, 1)  # mirror -- puts the text plaque on the board-facing side, matching the left panel
        right_x = self._geometry.board_origin_x + self._geometry.window_width
        right_panel.draw_on(canvas, right_x, 0)

        self._clean_canvas = canvas.img

    def reload(self) -> None:
        """Called only on a resize event — reloads at the current geometry size."""
        self.load()

    def fresh_canvas(self) -> Img:
        """Returns a new Img with a clean copy of the background and side
        panels — called at the start of every frame, before renderers
        (board, pieces, HUD text) draw on top of it."""
        canvas = Img()
        canvas.img = self._clean_canvas.copy()
        return canvas
