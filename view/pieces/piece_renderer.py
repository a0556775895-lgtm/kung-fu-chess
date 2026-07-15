class PieceRenderer:
    """Draws all live pieces every frame. Pulls frames from AnimationLibrary
    (memory only), and current position/state from PieceAnimator — doesn't
    touch disk and doesn't compute time/state itself."""

    def __init__(self, animation_library, piece_animator):
        """Store the animation library (frames) and piece animator (state/position) used for drawing."""
        self._library = animation_library
        self._animator = piece_animator

    def render(self, canvas, snapshot) -> None:
        """Draw every live piece in snapshot onto canvas."""
        for piece_snapshot in snapshot.pieces:
            self._draw_piece(canvas, piece_snapshot)

    def _draw_piece(self, canvas, piece_snapshot) -> None:
        """Draw a single piece's current animation frame at its current pixel position on canvas."""
        color = piece_snapshot.color.upper()
        visual_state = self._animator.get_visual_state(piece_snapshot)
        frame_index = self._animator.get_frame_index(piece_snapshot)

        clip = self._library.get_clip(piece_snapshot.kind, color, visual_state)
        frame_img = clip.frames[frame_index]

        x, y = self._animator.get_pixel_position(piece_snapshot)
        frame_img.draw_on(canvas, int(x), int(y))