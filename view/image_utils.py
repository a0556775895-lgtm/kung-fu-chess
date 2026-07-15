import cv2
import numpy as np


def ensure_alpha(img: np.ndarray) -> np.ndarray:
    """Ensures 4 channels (BGRA). If the image already has 4 channels,
    it's returned unchanged. Used before draw_on between images that may
    not have the same channel count (e.g. board.png without alpha + a
    piece with alpha) — so draw_on doesn't "drop" the piece's
    transparency (see the bug documented in the architecture doc)."""
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img