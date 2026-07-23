"""Render the winner-specific game-over artwork over the final board."""

from view import config
from view.img import Img


class GameOverRenderer:
    """Load both winner images once and select one from the final snapshot."""

    def __init__(
        self,
        geometry,
        white_win_path=config.GAME_OVER_WHITE_WIN_IMAGE_PATH,
        black_win_path=config.GAME_OVER_BLACK_WIN_IMAGE_PATH,
    ):
        """Store the canvas geometry and configurable asset paths."""
        self._geometry = geometry
        self._paths = {
            "w": white_win_path,
            "b": black_win_path,
        }
        self._images = {}

    def load(self) -> None:
        """Load both images, preserving their proportions within the window."""
        size = (self._geometry.canvas_width, self._geometry.canvas_height)
        self._images = {
            color: Img().read(path, size=size, keep_aspect=True)
            for color, path in self._paths.items()
        }

    def render(self, canvas, snapshot) -> None:
        """Overlay the artwork matching snapshot.winner_color after game over."""
        if not snapshot.game_over:
            return

        winner_image = self._images.get(snapshot.winner_color)
        if winner_image is None:
            return

        image_height, image_width = winner_image.img.shape[:2]
        x = (self._geometry.canvas_width - image_width) // 2
        y = (self._geometry.canvas_height - image_height) // 2
        winner_image.draw_on(canvas, x, y)
