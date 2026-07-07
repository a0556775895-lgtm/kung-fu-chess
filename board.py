class Board:
    def __init__(self, board_lines: list[str]):
        self._grid = []
        self._rows = 0
        self._cols = 0

        self._parse(board_lines)

    def _parse(self, board_lines: list[str]):
        first_row_width = None

        for row in board_lines:
            row = row.strip()

            if not row:
                continue

            tokens = row.split()

            if first_row_width is None:
                first_row_width = len(tokens)
            elif len(tokens) != first_row_width:
                raise ValueError("ROW_WIDTH_MISMATCH")

            self._validate_tokens(tokens)

            self._grid.append(tokens)

        self._rows = len(self._grid)
        self._cols = first_row_width if first_row_width is not None else 0

    def _validate_tokens(self, tokens: list[str]):
        for token in tokens:
            if token == ".":
                continue

            if len(token) != 2:
                raise ValueError("UNKNOWN_TOKEN")

            if token[0] not in ("w", "b"):
                raise ValueError("UNKNOWN_TOKEN")

    def print_board(self):
        for row in self._grid:
            print(" ".join(row))