import sys
from board import Board


def main():
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
        board = Board(board_lines)
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
            board.click(x, y)

        elif parts[0] == "wait":
            milliseconds = int(parts[1])
            board.wait(milliseconds)

        elif command == "print board":
            board.print_board()


if __name__ == "__main__":
    main()