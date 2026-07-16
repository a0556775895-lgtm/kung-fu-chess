# פרסור תסריטי בדיקה בפורמט Board:/Commands: (זהה לפורמט הקלט של main.py).
"""Parse a `.kfc` integration-test script into a board section and a list
of typed commands.

Script format (identical to the `Board:`/`Commands:` stdin format the
project's main loop understands):

    Board:
    wR . .
    . bK .
    Commands:
    click 0 0
    click 200 0
    wait 2000
    print board
    jump 100 0
"""

from dataclasses import dataclass


class ScriptParseError(ValueError):
    """Raised for malformed `.kfc` script text (not a board-content error --
    those come from BoardParser and are handled by script_runner)."""


@dataclass(frozen=True)
class ClickCommand:
    x: int
    y: int


@dataclass(frozen=True)
class JumpCommand:
    x: int
    y: int


@dataclass(frozen=True)
class WaitCommand:
    milliseconds: int


@dataclass(frozen=True)
class PrintBoardCommand:
    pass


Command = ClickCommand | JumpCommand | WaitCommand | PrintBoardCommand


@dataclass(frozen=True)
class ParsedScript:
    board_lines: list
    commands: list


def parse_script(text: str) -> ParsedScript:
    """Split `text` into board lines and a list of parsed Commands."""
    if "Board:" not in text:
        raise ScriptParseError("MISSING_BOARD_SECTION")

    board_section = text.split("Board:", 1)[1]

    if "Commands:" in board_section:
        board_text, commands_text = board_section.split("Commands:", 1)
    else:
        board_text, commands_text = board_section, ""

    board_lines = [line.strip() for line in board_text.strip().splitlines() if line.strip()]
    command_lines = [line.strip() for line in commands_text.strip().splitlines() if line.strip()]

    commands = [_parse_command_line(line) for line in command_lines]
    return ParsedScript(board_lines=board_lines, commands=commands)


def _parse_command_line(line: str) -> Command:
    if line == "print board":
        return PrintBoardCommand()

    parts = line.split()
    keyword = parts[0]

    if keyword == "click" and len(parts) == 3:
        return ClickCommand(x=int(parts[1]), y=int(parts[2]))
    if keyword == "jump" and len(parts) == 3:
        return JumpCommand(x=int(parts[1]), y=int(parts[2]))
    if keyword == "wait" and len(parts) == 2:
        return WaitCommand(milliseconds=int(parts[1]))

    raise ScriptParseError(f"UNKNOWN_COMMAND: {line!r}")
