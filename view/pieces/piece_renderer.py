class PieceRenderer:
    """מצייר את כל הכלים החיים בכל frame. שואב frames מ-AnimationLibrary
    (זיכרון בלבד), ומיקום/state נוכחיים מ-PieceAnimator - לא נוגע בדיסק
    ולא מחשב זמן/state בעצמו."""

    def __init__(self, animation_library, piece_animator):
        self._library = animation_library
        self._animator = piece_animator

    def render(self, canvas, snapshot) -> None:
        for piece_snapshot in snapshot.pieces:
            self._draw_piece(canvas, piece_snapshot)

    def _draw_piece(self, canvas, piece_snapshot) -> None:
        color = piece_snapshot.color.upper()
        visual_state = self._animator.get_visual_state(piece_snapshot)
        frame_index = self._animator.get_frame_index(piece_snapshot)

        clip = self._library.get_clip(piece_snapshot.kind, color, visual_state)
        frame_img = clip.frames[frame_index]

        x, y = self._animator.get_pixel_position(piece_snapshot)
        frame_img.draw_on(canvas, int(x), int(y))