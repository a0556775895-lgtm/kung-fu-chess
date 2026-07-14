# ייצוג כלי שחמט — זהות, צבע, סוג ומצב מחזור חיים (IDLE/MOVING/CAPTURED/AIRBORNE).
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
    IDLE = auto()        # עומד במקומו
    MOVING = auto()      # בתנועה ליעד
    CAPTURED = auto()    # נאכל, הוסר מהלוח
    AIRBORNE = auto()    # בקפיצה, חסין לתפיסה רגילה
    LONG_REST = auto()   # מנוחה אחרי מהלך רגיל, אסור לזוז
    SHORT_REST = auto()  # מנוחה אחרי קפיצה, אסור לזוז


@dataclass
class Piece:
    """A chess piece: identity (id, color, kind), current cell, and lifecycle state.

    Movement logic, timing, and legality belong to other layers.
    kind may change from 'P' to 'Q' on promotion (applied by RealTimeArbiter at arrival).
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

    def is_resting(self) -> bool:
        return self.state in (PieceState.LONG_REST, PieceState.SHORT_REST)

    def __str__(self) -> str:
        return f"{self.color}{self.kind}"