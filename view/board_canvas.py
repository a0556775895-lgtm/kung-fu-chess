import cv2
from .img import Img
from .sprite_loader import load_sprite


class BoardCanvas:
    def __init__(self, board_image_path: str, rows: int = 8, cols: int = 8,
                 target_size: tuple = (640, 640)):
        self.board = Img()
        self.board.read(board_image_path, size=target_size)

        if self.board.img.shape[2] == 3:
            self.board.img = cv2.cvtColor(self.board.img, cv2.COLOR_BGR2BGRA)

        # שומרים עותק "נקי" של רקע הלוח, בלי כלים -- כדי שכל render
        # יתחיל מחדש ולא יצייר כלים על גבי כלים מה-frame הקודם.
        self._clean_board = self.board.img.copy()

        board_h, board_w = self.board.img.shape[:2]
        self.rows = rows
        self.cols = cols
        self.cell_w = board_w // cols
        self.cell_h = board_h // rows

    def draw_piece(self, kind: str, color: str, row: int, col: int,
                   state: str = "idle", frame: int = 1):
        piece = load_sprite(kind, color, state, frame,
                             size=(self.cell_w, self.cell_h))
        x = col * self.cell_w
        y = row * self.cell_h
        piece.draw_on(self.board, x, y)

    def render_board(self, board):
        """מצייר את כל הכלים החיים על הלוח, לפי ה-grid האמיתי של Board."""
        self.board.img = self._clean_board.copy()  # מתחילים מרקע נקי

        for row in board.get_grid():
            for piece in row:
                if piece is None:
                    continue
                color_letter = str(piece.color).upper()  # 'w'/'b' -> 'W'/'B'
                self.draw_piece(
                    kind=piece.kind,
                    color=color_letter,
                    row=piece.cell.row,
                    col=piece.cell.col,
                )

    @property
    def image(self) -> Img:
        return self.board