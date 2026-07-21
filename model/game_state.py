# מצב גלובלי של המשחק — רק דגל game_over.
from dataclasses import dataclass, field

from model.piece import PieceColor


@dataclass
class GameState:
    """Authoritative game-level state; timing remains in RealTimeArbiter."""

    game_over: bool = False
    scores: dict[PieceColor, int] = field(default_factory=lambda: {
        PieceColor.WHITE: 0,
        PieceColor.BLACK: 0,
    })

    def add_score(self, color: PieceColor, points: int) -> None:
        """Credit points to one side after the engine resolves a capture."""
        self.scores[color] += points

    def snapshot_scores(self) -> dict[str, int]:
        """Return a detached, serialization-ready score mapping."""
        return {str(color): score for color, score in self.scores.items()}

    def end_game(self) -> None:
        """Mark the game as over."""
        self.game_over = True
