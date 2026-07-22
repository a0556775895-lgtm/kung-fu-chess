from dataclasses import dataclass
from model.position import Position


@dataclass(frozen=True)
class ClickCommand:
    position: Position


@dataclass(frozen=True)
class JumpCommand:
    position: Position


Command = ClickCommand | JumpCommand


class GameCommandSender:
    """Route view commands through an injected local engine or remote proxy."""

    def __init__(self, controller, game_engine):
        """Store the controller and game engine to dispatch commands to."""
        self._controller = controller
        self._game_engine = game_engine

    def send(self, command: Command) -> None:
        """Route left-click selection through Controller and jumps through the game API."""
        match command:
            case ClickCommand(position=position):
                self._controller.handle_click(position)
            case JumpCommand(position=position):
                self._game_engine.request_jump(position)
