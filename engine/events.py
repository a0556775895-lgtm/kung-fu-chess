"""The event vocabulary GameEngine publishes on its EventBus.

Mirrors the GameObserver Protocol (view/observer.py) one-to-one, so
GameEngine.subscribe() can adapt between the two without any consumer
(PieceAnimator, ScoreData, ...) needing to change.
"""

from dataclasses import dataclass

from model.position import Position
from realtime.real_time_arbiter import ArrivalEvent


@dataclass(frozen=True)
class MotionStarted:
    piece: object
    source: Position
    destination: Position
    duration_ms: int


@dataclass(frozen=True)
class JumpStarted:
    piece: object
    position: Position


@dataclass(frozen=True)
class Arrival:
    event: ArrivalEvent


@dataclass(frozen=True)
class GameStarted:
    pass


@dataclass(frozen=True)
class GameOver:
    pass
