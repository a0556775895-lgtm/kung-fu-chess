# הרצת תסריט בדיקה דרך נתיב הפקודות האמיתי (BoardParser -> GameEngine/Controller).
"""Run a parsed `.kfc` script through the real command path -- the same
objects `view.display_manager.DisplayManager` wires up -- and return the
combined stdout produced by `print board` commands.

click/wait go through `Controller` exactly like a left-click in the real
UI. jump bypasses the Controller's selection state and calls
`GameEngine.request_jump` directly, mirroring how a right-click is
dispatched in `view/input/commands.py::LocalCommandSender`.

A board that fails to parse (`UNKNOWN_TOKEN` / `ROW_WIDTH_MISMATCH`)
produces a single `ERROR <reason>` line and no commands are run, matching
the historical stdin-driven `main.py` behavior described in the README.
"""

import contextlib
import io

from boardio.board_parser import BoardParser
from boardio.board_printer import print_board
from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller

from texttests.script_parser import (
    ClickCommand,
    JumpCommand,
    ParsedScript,
    PrintBoardCommand,
    WaitCommand,
    parse_script,
)

CELL_SIZE = 100


def run_script(script_text: str) -> str:
    """Parse and execute `script_text`; return everything it printed."""
    return run_parsed_script(parse_script(script_text))


def run_parsed_script(parsed: ParsedScript) -> str:
    """Execute an already-parsed script; return everything it printed."""
    output = io.StringIO()

    try:
        board = BoardParser.parse(parsed.board_lines)
    except ValueError as error:
        output.write(f"ERROR {error}\n")
        return output.getvalue()

    engine = GameEngine(board)
    mapper = BoardMapper(board.rows, board.cols, cell_size=CELL_SIZE)
    controller = Controller(board, engine, mapper)

    for command in parsed.commands:
        _run_command(command, board, engine, mapper, controller, output)

    return output.getvalue()


def _run_command(command, board, engine, mapper, controller, output):
    if isinstance(command, ClickCommand):
        controller.handle_pixel_click(command.x, command.y)
    elif isinstance(command, JumpCommand):
        _run_jump(command, engine, mapper)
    elif isinstance(command, WaitCommand):
        engine.wait(command.milliseconds)
    elif isinstance(command, PrintBoardCommand):
        with contextlib.redirect_stdout(output):
            print_board(board.get_grid())


def _run_jump(command, engine, mapper):
    position = mapper.pixel_to_position(command.x, command.y)
    if mapper.is_inside_board(position):
        engine.request_jump(position)
