from boardio.board_parser import BoardParser
from .board_canvas import BoardCanvas

STANDARD_OPENING = [
    "bR bN bB bQ bK bB bN bR",
    "bP bP bP bP bP bP bP bP",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    ".  .  .  .  .  .  .  .",
    "wP wP wP wP wP wP wP wP",
    "wR wN wB wQ wK wB wN wR",
]


class ImageView:
    def __init__(self):
        self.board = BoardParser.parse(STANDARD_OPENING)
        self.canvas = BoardCanvas(r"view\assest\board.png")
        self.canvas.render_board(self.board)

    def show(self):
        self.canvas.image.show()