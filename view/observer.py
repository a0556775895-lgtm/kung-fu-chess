from typing import Protocol
from realtime.real_time_arbiter import ArrivalEvent
from model.position import Position


class GameObserver(Protocol):
    """Anyone who wants to 'listen' to game events registers via
    GameEngine.subscribe(). Replaces ugly polling of the snapshot every frame."""

    def on_arrival(self, event: ArrivalEvent) -> None:
        """Called on every move that reaches its destination — even without a capture."""
        ...

    def on_motion_started(self, piece, source: Position,
                           destination: Position, duration_ms: int) -> None:
        """Called when a regular motion starts — needed for visual interpolation."""
        ...

    def on_jump_started(self, piece, position: Position) -> None:
        """Called when a jump starts. Duration is always fixed (config.JUMP_DURATION_MS)."""
        ...

    def on_game_over(self) -> None:
        """Called once, when a king is captured."""
        ...