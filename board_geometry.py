class BoardGeometry:
    """Manage board shape and pixel-to-cell translation."""

    def __init__(self, rows, cols, cell_size=100):
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size

    def update_dimensions(self, rows, cols):
        self.rows = rows
        self.cols = cols

    def pixel_to_cell(self, x, y):
        return y // self.cell_size, x // self.cell_size

    def is_inside_board(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.cols
