from Piece import Piece


class Rook(Piece):
    """Represents a rook chess piece."""

    def __init__(self, color):
        super().__init__(color, "R", 2000)

    def is_valid_move(self, source_row, source_col, destination_row, destination_col):
        row_distance = abs(destination_row - source_row)
        col_distance = abs(destination_col - source_col)

        return (
            (row_distance == 0 and col_distance > 0) or
            (col_distance == 0 and row_distance > 0)
        )
    
    def get_path_cells(
    self,
    source_row,
    source_col,
    destination_row,
    destination_col,
    ):
        path = []

        if source_row == destination_row:
            step = 1 if destination_col > source_col else -1

            for col in range(source_col + step, destination_col, step):
                path.append((source_row, col))

        else:
            step = 1 if destination_row > source_row else -1

            for row in range(source_row + step, destination_row, step):
                path.append((row, source_col))

        return path