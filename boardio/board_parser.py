# פרסור טקסט ללוח שחמט ויצירת אובייקט Board.
"""Parse a text board definition into a Board instance."""

from model.position import Position
from rules.piece_factory import PieceFactory
from model.board import Board
class BoardParser:
    @staticmethod
    def parse(board_lines):
        """Creates a Board instance from textual input."""  
        grid = []
        firstrow_width = None

        for row_index, row in enumerate(board_lines):
            tokens = row.split()

            if firstrow_width is None:
                firstrow_width = len(tokens)
            elif len(tokens) != firstrow_width:
                raise ValueError("ROW_WIDTH_MISMATCH")

            currentrow = []

            for col_index, token in enumerate(tokens):
                if token == ".":
                    currentrow.append(None)
                else:
                    piece = PieceFactory.create_piece(
                        token, cell=Position(row_index, col_index)
                    )
                    currentrow.append(piece)

            grid.append(currentrow)

        rows = len(grid)
        cols = firstrow_width

        return Board(grid, rows, cols)