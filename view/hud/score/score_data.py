# צובר ניקוד לכל צד לפי כלים שנתפסו — GameObserver, לא נוגע בציור.
"""Tracks each side's capture score. Subscribes as a GameObserver and
reacts only to on_arrival — never touches the board or the canvas.
ScoreRenderer reads white_score/black_score off this each frame."""

from model.piece import PieceColor, PieceState

# Standard chess piece values. King is 0 -- its capture ends the game
# via GameEngine.game_over, not scoring.
PIECE_VALUES = {
    "P": 1,
    "N": 3,
    "B": 3,
    "R": 5,
    "Q": 9,
    "K": 0,
}


class ScoreData:
    """Accumulates each side's score, credited for every enemy piece it captures."""

    def __init__(self):
        self._scores = {PieceColor.WHITE: 0, PieceColor.BLACK: 0}

    @property
    def white_score(self) -> int:
        """Total points White has scored from captures."""
        return self._scores[PieceColor.WHITE]

    @property
    def black_score(self) -> int:
        """Total points Black has scored from captures."""
        return self._scores[PieceColor.BLACK]

    # --- GameObserver ---

    def on_arrival(self, event) -> None:
        """Credit whichever side actually did the capturing with the victim's point value."""
        victim, capturer_color = self._resolve_capture(event)
        if victim is not None:
            self._scores[capturer_color] += PIECE_VALUES[victim.kind]

    def on_motion_started(self, piece, source, destination, duration_ms) -> None:
        """No-op: scoring only cares about arrivals."""
        pass

    def on_jump_started(self, piece, position) -> None:
        """No-op: scoring only cares about arrivals."""
        pass

    def on_game_over(self) -> None:
        """No-op: score is already final by the time the game ends."""
        pass

    # --- internal ---

    @staticmethod
    def _resolve_capture(event):
        """Return (victim_piece, capturer_color), or (None, None) for a plain move.

        Usually event.piece is the mover and event.captured_piece is the
        victim. The one exception is an airborne capture
        (RealTimeArbiter._resolve_arrivals): there the *arriving* piece is
        the one removed, and event.captured_piece actually holds the
        surviving airborne piece that did the capturing.
        """
        if event.piece.state == PieceState.CAPTURED:
            return event.piece, event.captured_piece.color
        if event.captured_piece is not None:
            return event.captured_piece, event.piece.color
        return None, None
