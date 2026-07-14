from .img import Img

ASSETS_ROOT = r"view\assest\pieces3"


def sprite_path(kind: str, color: str, state: str, frame: int) -> str:
    """kind: 'R','N','B','Q','K','P'. color: 'W' or 'B'. frame: 1-based."""
    folder = f"{kind}{color}"
    return rf"{ASSETS_ROOT}\{folder}.png"


def load_sprite(kind: str, color: str, state: str, frame: int, size=None) -> Img:
    img = Img()
    img.read(sprite_path(kind, color, state, frame), size=size, keep_aspect=True)
    return img