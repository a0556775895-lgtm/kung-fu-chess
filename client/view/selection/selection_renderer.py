class SelectionRenderer:
    """מצייר הדגשה על התא הנבחר, אם יש כזה. תלוי רק ב-geometry
    (למיקום), לא בלוח ולא בכלים - רכיב עצמאי לגמרי."""

    def __init__(self, highlight_loader, geometry):
        self._highlight_loader = highlight_loader
        self._geometry = geometry

    def render(self, canvas, snapshot) -> None:
        if snapshot.selected_cell is None:
            return
        x, y = self._geometry.cell_to_pixel(snapshot.selected_cell)
        self._highlight_loader.image.draw_on(canvas, x, y)