from ..img import Img
from ..image_utils import ensure_alpha
from .. import config


class HighlightLoader:
    def __init__(self, geometry, image_path=config.HIGHLIGHT_IMAGE_PATH):
        self._geometry = geometry
        self._image_path = image_path
        self._highlight_img = None

    def load(self) -> None:
        img = Img()
        img.read(str(self._image_path),
                  size=(self._geometry.cell_w, self._geometry.cell_h),
                  keep_aspect=True)
        img.img = ensure_alpha(img.img)
        self._highlight_img = img

    def reload(self) -> None:
        self.load()

    @property
    def image(self) -> Img:
        return self._highlight_img