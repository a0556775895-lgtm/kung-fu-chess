# מצב גלובלי של המשחק — רק דגל game_over.
from dataclasses import dataclass


@dataclass
class GameState:
    """Tracks whether the game has ended. Timing lives in RealTimeArbiter."""

    game_over: bool = False

    def end_game(self) -> None:
        self.game_over = True