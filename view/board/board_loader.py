from ..img import Img
from ..image_utils import ensure_alpha
from .. import config


class BoardLoader:
    """טוען את board.png פעם אחת, לפי הגודל הנוכחי ב-geometry
    (לא קבוע נפרד - כדי שלוח וגיאומטריה לא 'יתפצלו' לגדלים שונים).
    שומר עותק 'נקי' (ללא כלים) לשימוש חוזר בכל frame."""

    def __init__(self, geometry, image_path=config.BOARD_IMAGE_PATH):
        self._geometry = geometry
        self._image_path = image_path
        self._clean_board = None
        # אין קריאה ל-load() כאן - הבנייה זולה, הטעינה מפורשת

    def load(self) -> None:
        board = Img()
        board.read(
            str(self._image_path),
            size=(self._geometry.window_width, self._geometry.window_height),
        )
        board.img = ensure_alpha(board.img)
        self._clean_board = board.img.copy()

    def reload(self) -> None:
        """נקרא רק באירוע resize - טוען מחדש לפי הגודל העדכני ב-geometry."""
        self.load()

    def fresh_canvas(self) -> Img:
        """מחזיר Img חדש עם עותק נקי של הלוח - נקרא בתחילת כל frame,
        לפני שה-renderers מציירים עליו כלים."""
        canvas = Img()
        canvas.img = self._clean_board.copy()
        return canvas