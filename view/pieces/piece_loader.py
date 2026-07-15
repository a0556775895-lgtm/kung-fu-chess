from pathlib import Path
from ..img import Img
from .. import config


class PieceLoader:
    """Loads a single sprite from disk. Converts the model's convention
    (Color+Kind, e.g. 'wP') to the assets folder convention (Kind+Color,
    e.g. 'PW')."""

    def __init__(self, assets_root: Path = config.ASSETS_ROOT):
        self._assets_root = assets_root

    def sprite_path(self, kind: str, color: str, state: str, frame: int) -> Path:
        folder = f"{kind}{color}"
        return self._assets_root / folder / "states" / state / "sprites" / f"{frame}.png"

    def load_frame(self, kind: str, color: str, state: str, frame: int,
                   cell_size: tuple[int, int]) -> Img:
        img = Img()
        img.read(str(self.sprite_path(kind, color, state, frame)),
                  size=cell_size, keep_aspect=True)
        return img

    def count_frames(self, kind: str, color: str, state: str) -> int:
        """Counts actual files in the folder — doesn't rely on a fixed
        number (5), so it doesn't break if someone adds/removes a frame."""
        sprites_dir = self._assets_root / f"{kind}{color}" / "states" / state / "sprites"
        return len(list(sprites_dir.glob("*.png")))

    @staticmethod
    def asset_color(piece_snapshot) -> str:
        """
        Converts 'w'/'b' (the model's PieceColor convention) to 'W'/'B'.
        """
        return piece_snapshot.color.upper()