"""Typed game events shared by the server and remote client."""

from dataclasses import dataclass

from networking.models.position import Position


@dataclass(frozen=True)
class ArrivalEvent:
    piece: object
    source: object
    destination: object
    captured_piece: object | None


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
    duration_ms: int


@dataclass(frozen=True)
class Arrival:
    event: ArrivalEvent


@dataclass(frozen=True)
class GameStarted:
    pass


@dataclass(frozen=True)
class GameOver:
    pass
