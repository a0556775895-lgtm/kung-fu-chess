import cv2
import numpy as np


def ensure_alpha(img: np.ndarray) -> np.ndarray:
    """מבטיח 4 ערוצים (BGRA). אם התמונה כבר 4 ערוצים - מוחזרת ללא שינוי.
    שימוש: לפני draw_on בין תמונות שאולי לא זהות במספר הערוצים
    (למשל board.png בלי אלפא + כלי עם אלפא) - כדי ש-draw_on
    לא "יזרוק" את שקיפות הכלי (ראו התקלה שתועדה במסמך הארכיטקטורה)."""
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img