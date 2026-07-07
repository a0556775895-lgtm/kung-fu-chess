import sys

from board import Board


def extract_board_lines(input_data: str) -> list[str]:
    if "Board:" not in input_data:
        return []

    board_section = input_data.split("Board:")[1].split("Commands:")[0]

    return board_section.strip().splitlines()


def main():
    input_data = sys.stdin.read()

    board_lines = extract_board_lines(input_data)

    try:
        board = Board(board_lines)
        board.print_board()
    except ValueError as error:
        print(f"ERROR {error}")


if __name__ == "__main__":
    main()