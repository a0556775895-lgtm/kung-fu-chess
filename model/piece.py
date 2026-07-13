from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from model.position import Position


class PieceColor(Enum):
    WHITE = "w"
    BLACK = "b"

    def __str__(self) -> str:
        return self.value


class PieceState(Enum):
    IDLE = auto()
    MOVING = auto()
    CAPTURED = auto()
    AIRBORNE = auto()


@dataclass
class Piece:
    """Represents a chess piece.

    Stores only the piece identity and logical runtime state.
    Movement logic, timing and legality belong to other layers.
    """

    id: str
    color: PieceColor
    kind: str
    cell: Position | None = None
    state: PieceState = PieceState.IDLE


    def is_moving(self) -> bool:
        return self.state is PieceState.MOVING

    def is_airborne(self) -> bool:
        return self.state is PieceState.AIRBORNE

    def __str__(self) -> str:
        return f"{self.color}{self.kind}"