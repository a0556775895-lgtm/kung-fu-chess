from ..img import Img
from ..image_utils import ensure_alpha
from .. import config


class BoardLoader:
    """Loads board.png once, sized to the current geometry (not a
    separate constant — so the board and geometry never 'drift' to
    different sizes). Pure Loader -- doesn't draw. See BoardRenderer
    for the per-frame draw, same split as HighlightLoader/SelectionRenderer."""

    def __init__(self, geometry, image_path=config.BOARD_IMAGE_PATH):
        """Store geometry and image path; no board image is loaded yet."""
        self._geometry = geometry
        self._image_path = image_path
        self._board_img = None
        # No call to load() here — construction is cheap, loading is explicit

    def load(self) -> None:
        """Load the board image sized to the current geometry."""
        img = Img()
        img.read(
            str(self._image_path),
            size=(self._geometry.window_width, self._geometry.window_height),
        )
        img.img = ensure_alpha(img.img)
        self._board_img = img

    def reload(self) -> None:
        """Called only on a resize event — reloads at the current geometry size."""
        self.load()

    @property
    def image(self) -> Img:
        """The loaded board image, ready to be drawn."""
        return self._board_img
