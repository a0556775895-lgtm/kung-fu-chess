from piece import Piece


class Bishop(Piece):
    """Represents a bishop chess piece."""

    def __init__(self, color):
        super().__init__(color, "B", 1000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return row_distance == col_distance and row_distance > 0
    

    def get_path_cells(
    self,
    source_row,
    source_col,
    destination_row,
    destination_col,
    destination_piece
    ):
        path = []

        row_step = 1 if destination_row > source_row else -1
        col_step = 1 if destination_col > source_col else -1

        row = source_row + row_step
        col = source_col + col_step

        while row != destination_row:
            path.append((row, col))
            row += row_step
            col += col_step

        return path