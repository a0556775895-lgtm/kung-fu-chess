"""Immutable description of one completed server-side game."""

from dataclasses import dataclass
from enum import Enum

from model.piece import PieceColor


class FinishReason(str, Enum):
    """The server-recognized reasons a game may end."""

    KING_CAPTURE = "KING_CAPTURE"
    RESIGN = "RESIGN"
    DISCONNECT = "DISCONNECT"


@dataclass(frozen=True, slots=True)
class GameResult:
    """The winner, reason and authoritative duration of a completed game."""

    winner_color: PieceColor
    reason: FinishReason
    duration_ms: int

    def __post_init__(self) -> None:
        """Reject incomplete result objects before they reach persistence."""
        if not isinstance(self.winner_color, PieceColor):
            raise ValueError("INVALID_WINNER_COLOR")
        if not isinstance(self.reason, FinishReason):
            raise ValueError("INVALID_FINISH_REASON")
        if (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, int)
            or self.duration_ms < 0
        ):
            raise ValueError("INVALID_GAME_DURATION")
