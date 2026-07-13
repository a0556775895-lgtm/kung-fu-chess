from dataclasses import dataclass


@dataclass
class GameState:
    """Holds game-wide state shared across the engine.

    Timing lives in RealTimeArbiter, not here. GameState only tracks
    whether the game has ended.
    """

    game_over: bool = False

    def end_game(self) -> None:
        self.game_over = True