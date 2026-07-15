from dataclasses import dataclass
from model.position import Position


@dataclass(frozen=True)
class ClickCommand:
    position: Position


@dataclass(frozen=True)
class JumpCommand:
    position: Position


Command = ClickCommand | JumpCommand


class LocalCommandSender:
    """המימוש היחיד כרגע: קורא ישירות ל-Controller/GameEngine המקומיים.
    כשיגיע יום ומשחק מרובה-משתתפים יידרש, NetworkCommandSender יחליף
    רק את המחלקה הזו - בלי לגעת ב-extractor או ב-display_manager."""

    def __init__(self, controller, game_engine):
        self._controller = controller
        self._game_engine = game_engine

    def send(self, command: Command) -> None:
        match command:
            case ClickCommand(position=position):
                self._controller.handle_click(position)
            case JumpCommand(position=position):
                self._game_engine.request_jump(position)