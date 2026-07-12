# Git repository: https://github.com/a0556775895-lgtm/kung-fu-chess

import sys
from engine.game_engine import GameEngine


def main():
    """Entry point: parse input and run commands on a `GameEngine`.

    Input should contain a `Board:` section and optional `Commands:` section.

    STEP 10 CHANGE: was `from model.board import Board` / `Board(board_lines)`.
    main.py now talks to `GameEngine`, which owns the game-over decision
    (see engine/game_engine.py). GameEngine mirrors Board's public surface
    1:1, so nothing else in this function needed to change -- the
    `try/except ValueError` still works unmodified because `GameEngine.__init__`
    builds a `Board` internally and the parse error propagates through it
    exactly as before.
    """

    input_data = sys.stdin.read()

    if "Board:" not in input_data:
        return

    board_section = input_data.split("Board:")[1]

    if "Commands:" in board_section:
        board_text, commands_text = board_section.split("Commands:")
    else:
        board_text = board_section
        commands_text = ""

    board_lines = [
        line.strip()
        for line in board_text.strip().split("\n")
        if line.strip()
    ]

    try:
        game = GameEngine(board_lines)
    except ValueError as error:
        if str(error) == "UNKNOWN_TOKEN":
            print("ERROR UNKNOWN_TOKEN")
        elif str(error) == "ROW_WIDTH_MISMATCH":
            print("ERROR ROW_WIDTH_MISMATCH")
        return

    commands = [
        line.strip()
        for line in commands_text.strip().split("\n")
        if line.strip()
    ]

    for command in commands:
        parts = command.split()

        if parts[0] == "click":
            x = int(parts[1])
            y = int(parts[2])
            game.click(x, y)

        elif parts[0] == "wait":
            milliseconds = int(parts[1])
            game.wait(milliseconds)

        elif command == "print board":
            game.print_board()

        elif parts[0] == "jump":
            x = int(parts[1])
            y = int(parts[2])
            game.jump(x, y)


if __name__ == "__main__":
    main()