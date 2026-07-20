"""Plays a sound for each notable game event.

Subscribes directly to the raw EventBus (GameEngine.bus), not through
the GameObserver protocol, since it needs to distinguish event types
(e.g. capture vs. plain arrival) rather than react to all four.
"""

import logging
import winsound

from engine.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from view import config

logger = logging.getLogger(__name__)

_SOUND_FILE_BY_EVENT = {
    MotionStarted: "click.wav",
    JumpStarted: "jump.wav",
    GameStarted: "opening.wav",
    GameOver: "game_over.wav",
}


class SoundPlayer:
    def __init__(self, bus):
        """Register a handler per event type that has an associated sound."""
        self._cancellations = []
        for event_type, filename in _SOUND_FILE_BY_EVENT.items():
            cancel = bus.subscribe(event_type, self._handler_for(filename))
            self._cancellations.append(cancel)
        self._cancellations.append(bus.subscribe(Arrival, self._on_arrival))

    def close(self) -> None:
        """Stop listening to game events. Safe to call more than once."""
        for cancel in self._cancellations:
            cancel()

    def _handler_for(self, filename):
        """Return a bus handler that always plays filename, ignoring the event's own fields."""
        return lambda _event: self._play(filename)

    def _on_arrival(self, event) -> None:
        """Only arrivals that captured a piece get a sound; plain arrivals are silent."""
        if event.event.captured_piece is not None:
            self._play("eat.wav")

    def _play(self, filename: str) -> None:
        path = config.SOUNDS_ROOT / filename
        if not path.exists():
            logger.debug("sound asset missing, skipping: %s", path)
            return
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            logger.warning("failed to play sound: %s", path, exc_info=True)
