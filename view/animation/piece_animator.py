from dataclasses import dataclass
from model.position import Position
from rules import piece_rules
from .. import config
from ..pieces.piece_loader import PieceLoader

# Visual states whose real duration is dictated by the model's rest
# cooldown (RealTimeArbiter), not by however many frames the clip has -
# so the piece can't look ready to move before it actually is.
_STATE_DURATION_MS = {
    "long_rest": piece_rules.get_long_rest_duration(),
    "short_rest": piece_rules.get_short_rest_duration(),
}

#TODO: update the calls to change color to UPPER via a function
@dataclass
class _TrackedPiece:
    visual_state: str = "idle"
    elapsed_in_state_ms: int = 0
    motion_source: Position = None
    motion_destination: Position = None
    motion_duration_ms: int = None


class PieceAnimator:
    """Maps PieceState (model) + on_motion_started/on_jump_started events
    to a visual state, current frame, and pixel position (with interpolation
    while moving). Receives the same dt_ms fed into game_engine.wait() —
    not a separate real clock."""

    def __init__(self, animation_library, geometry):
        self._library = animation_library
        self._geometry = geometry
        self._tracked: dict[str, _TrackedPiece] = {}

    # --- GameObserver callbacks ---

    def on_motion_started(self, piece, source, destination, duration_ms) -> None:
        self._tracked[piece.id] = _TrackedPiece(
            visual_state="move",
            motion_source=source,
            motion_destination=destination,
            motion_duration_ms=duration_ms,
        )

    def on_jump_started(self, piece, position) -> None:
        self._tracked[piece.id] = _TrackedPiece(
            visual_state="jump",
            motion_source=position,
            motion_destination=position,
            motion_duration_ms=config.JUMP_DURATION_MS,
        )

    def on_arrival(self, event) -> None:
        pass  # actual cleanup happens in update(), based on snapshot membership — not here

    def on_game_over(self) -> None:
        pass

    # --- per-frame update ---

    def update(self, dt_ms: int, snapshot) -> None:
        live_ids = {p.id for p in snapshot.pieces}
        for stale_id in set(self._tracked) - live_ids:
            del self._tracked[stale_id]     # a piece that vanished silently (collision/capture) is cleaned up here

        for piece_snapshot in snapshot.pieces:
            tracked = self._tracked.setdefault(piece_snapshot.id, _TrackedPiece())
            tracked.elapsed_in_state_ms += dt_ms
            self._advance_if_finished(piece_snapshot, tracked)

    def _advance_if_finished(self, piece_snapshot, tracked) -> None:
        clip = self._library.get_clip(piece_snapshot.kind,
                                       piece_snapshot.color.upper(),
                                       tracked.visual_state)
        if tracked.motion_duration_ms is not None:
            duration_ms = tracked.motion_duration_ms
        elif clip.state_config.graphics.is_loop:
            return
        else:
            duration_ms = 1000 * len(clip.frames) / clip.state_config.graphics.frames_per_sec
        if tracked.elapsed_in_state_ms >= duration_ms:
            next_state = clip.state_config.physics.next_state_when_finished
            tracked.visual_state = next_state
            tracked.elapsed_in_state_ms = 0
            tracked.motion_source = tracked.motion_destination = None
            tracked.motion_duration_ms = _STATE_DURATION_MS.get(next_state)

    # --- queries for PieceRenderer ---

    def get_visual_state(self, piece_snapshot) -> str:
        tracked = self._tracked.get(piece_snapshot.id)
        return tracked.visual_state if tracked else "idle"

    def get_frame_index(self, piece_snapshot) -> int:
        tracked = self._tracked.get(piece_snapshot.id)
        state = tracked.visual_state if tracked else "idle"
        elapsed = tracked.elapsed_in_state_ms if tracked else 0
        clip = self._library.get_clip(piece_snapshot.kind, piece_snapshot.color.upper(), state)
        raw_index = int(elapsed * clip.state_config.graphics.frames_per_sec / 1000)
        if clip.state_config.graphics.is_loop:
            return raw_index % len(clip.frames)
        return min(raw_index, len(clip.frames) - 1)

    def get_pixel_position(self, piece_snapshot) -> tuple[float, float]:
        tracked = self._tracked.get(piece_snapshot.id)
        if tracked is None or tracked.visual_state != "move":
            return self._geometry.cell_to_pixel(piece_snapshot.cell)

        progress = min(tracked.elapsed_in_state_ms / tracked.motion_duration_ms, 1.0)
        x0, y0 = self._geometry.cell_to_pixel(tracked.motion_source)
        x1, y1 = self._geometry.cell_to_pixel(tracked.motion_destination)
        return (x0 + (x1 - x0) * progress, y0 + (y1 - y0) * progress)