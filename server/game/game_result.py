"""Immutable description of one completed server-side game."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from model.piece import PieceColor


class FinishReason(str, Enum):
    """The server-recognized reasons a game may end."""

    KING_CAPTURE = "KING_CAPTURE"
    RESIGN = "RESIGN"
    DISCONNECT = "DISCONNECT"


@dataclass(frozen=True, slots=True)
class GameResult:
    """The winner, reason and absolute UTC time of a completed game."""

    winner_color: PieceColor
    reason: FinishReason
    ended_at: datetime

    def __post_init__(self) -> None:
        """Reject incomplete result objects before they reach persistence."""
        if not isinstance(self.winner_color, PieceColor):
            raise ValueError("INVALID_WINNER_COLOR")
        if not isinstance(self.reason, FinishReason):
            raise ValueError("INVALID_FINISH_REASON")
        if not isinstance(self.ended_at, datetime) or self.ended_at.utcoffset() is None:
            raise ValueError("END_TIME_MUST_BE_TIMEZONE_AWARE")
