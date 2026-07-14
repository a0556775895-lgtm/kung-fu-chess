# """Entry point: parse input and run commands through the real
# Controller -> GameEngine -> Renderer path.

# Input should contain a `Board:` section and optional `Commands:`
# section.
# """

# import sys

# from boardio.board_parser import BoardParser
# from engine.game_engine import GameEngine
# from input.board_mapper import BoardMapper
# from input.controller import Controller
# from view.renderer import render_snapshot


# def main():
#     input_data = sys.stdin.read()

#     if "Board:" not in input_data:
#         return

#     board_section = input_data.split("Board:")[1]

#     if "Commands:" in board_section:
#         board_text, commands_text = board_section.split("Commands:")
#     else:
#         board_text = board_section
#         commands_text = ""

#     board_lines = [
#         line.strip()
#         for line in board_text.strip().split("\n")
#         if line.strip()
#     ]

#     try:
#         board = BoardParser.parse(board_lines)
#     except ValueError as error:
#         print(f"ERROR {error}")
#         return

#     game_engine = GameEngine(board)
#     board_mapper = BoardMapper(board.rows, board.cols)
#     controller = Controller(board, game_engine, board_mapper)

#     commands = [
#         line.strip()
#         for line in commands_text.strip().split("\n")
#         if line.strip()
#     ]

#     for command in commands:
#         parts = command.split()

#         if parts[0] == "jump":
#             x = int(parts[1])
#             y = int(parts[2])
#             game_engine.request_jump(board_mapper.pixel_to_position(x, y))

#         elif parts[0] == "click":
#             x = int(parts[1])
#             y = int(parts[2])
#             controller.handle_pixel_click(x, y)

#         elif parts[0] == "wait":
#             milliseconds = int(parts[1])
#             game_engine.wait(milliseconds)

#         elif command == "print board":
#             render_snapshot(game_engine.snapshot())

from view.image_view import ImageView

if __name__ == "__main__":  # pragma: no cover
    # main()
    view = ImageView()
    view.show()