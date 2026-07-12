import io
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from boardio.board_parser import parse_board
from boardio.board_printer import print_board as print_grid
from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller
from model.board import Board
from model.game_state import GameState
from model.piece import Piece, PieceColor, PieceState
from model.position import Position
from realtime.motion import Motion
from realtime.real_time_arbiter import RealTimeArbiter
from rules import piece_rules
from rules.piece_factory import PieceFactory
from rules.rule_engine import (
    EmptyCellError,
    FriendlyFireError,
    IllegalPatternError,
    OutOfBoardError,
    PathBlockedError,
    PieceAlreadyMovingError,
    RuleViolation,
    validate_move,
)
from view.renderer import print_rule_violation, render_rule_violation
import main as main_module


class FakeBoard:
    def __init__(self, grid, rows=1, cols=1):
        self._grid = grid
        self._rows = rows
        self._cols = cols

    def get_piece_at(self, position):
        return self._grid[position.row][position.col]

    def is_inside_board(self, position):
        return 0 <= position.row < self._rows and 0 <= position.col < self._cols

    def get_rows(self):
        return self._rows


class DummyRuleViolation(RuleViolation):
    pass


def make_board(lines):
    return Board(lines)


def test_piece_position_and_state_lifecycle():
    piece = Piece(PieceColor.WHITE, "P", cell=Position(3, 4), id="custom")
    assert piece.id == "custom"
    assert piece.color == PieceColor.WHITE
    assert piece.color == "w"
    assert piece.kind == "P"
    assert piece.cell == Position(3, 4)
    assert piece.state == PieceState.IDLE
    assert not piece.is_moving()

    piece.set_cell(Position(5, 6))
    assert piece.cell == Position(5, 6)

    piece.start_move()
    assert piece.is_moving()
    piece.finish_move()
    assert piece.state == PieceState.IDLE

    piece.start_jump(10)
    assert piece.is_airborne()
    assert piece.should_finish_jump(9) is False
    assert piece.should_finish_jump(10 + piece_rules.get_jump_duration("P")) is True
    piece.finish_jump()
    assert not piece.is_airborne()

    assert piece.is_royal() is False

    king = Piece(PieceColor.BLACK, "K", cell=Position(0, 0))
    assert king.is_royal() is True

    assert str(piece) == "wP"
    assert "Piece(id='custom'" in repr(piece)

    assert hash(Position(1, 2)) == hash(Position(1, 2))
    row, col = Position(1, 2)
    assert (row, col) == (1, 2)


def test_game_state_and_board_core_operations():
    game_state = GameState()
    game_state.advance_time(50)
    assert game_state.current_time == 50
    assert game_state.game_over is False
    game_state.end_game()
    assert game_state.game_over is True

    board = make_board(["wR . .", ". . ."])
    assert board.get_rows() == 2
    assert board.get_grid()[0][0].kind == "R"
    assert board.get_piece_at(Position(0, 0)).kind == "R"
    assert board.is_inside_board(Position(0, 0)) is True
    assert board.is_inside_board(Position(2, 0)) is False

    board.place_piece(Position(1, 1), Piece(PieceColor.BLACK, "P"))
    assert board.get_piece_at(Position(1, 1)) is not None
    board.remove_piece(Position(1, 1))
    assert board.get_piece_at(Position(1, 1)) is None

    board.end_game()
    assert board.game_over is True
    assert board.consume_royal_capture() is False

    board.wait(100)
    assert board.current_time == 100

    source = Position(0, 0)
    destination = Position(0, 2)
    board.schedule_move(source, destination, 10, 20)
    piece = board.get_piece_at(source)
    assert piece.is_moving() is True
    assert board._arbiter.has_active_motion(piece) is True

    board.jump(0, 0)
    assert board.get_piece_at(Position(0, 0)) is not None


def test_board_parser_printer_and_mapper():
    grid, rows, cols = parse_board(["wP .", ". bP"])
    assert rows == 2
    assert cols == 2
    assert str(grid[0][0]) == "wP"
    assert grid[1][1].kind == "P"

    with pytest.raises(ValueError, match="ROW_WIDTH_MISMATCH"):
        parse_board(["wP", ". ."])

    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        parse_board(["wX"])

    mapper = BoardMapper(2, 3, cell_size=100)
    assert mapper.pixel_to_position(250, 150) == Position(1, 2)
    mapper.update_dimensions(4, 5)
    assert mapper.is_inside_board(Position(3, 4)) is True
    assert mapper.is_inside_board(Position(4, 5)) is False

    output = io.StringIO()
    import contextlib

    with contextlib.redirect_stdout(output):
        print_grid(grid)
    assert output.getvalue().strip().splitlines()[0] == "wP ."


def test_piece_rules_and_rule_engine_validation():
    white = PieceColor.WHITE
    black = PieceColor.BLACK
    assert piece_rules.get_move_time("N") == 3000
    assert piece_rules.get_jump_duration("Q") == 1000
    assert piece_rules.is_royal("K") is True
    assert piece_rules.is_royal("P") is False

    source = Position(1, 1)
    destination = Position(0, 1)
    assert piece_rules.is_valid_move("P", white, source, destination, None, 8) is True
    assert piece_rules.is_valid_move("P", white, source, Position(2, 1), None, 8) is False
    assert piece_rules.is_valid_move("P", white, source, Position(0, 0), Piece(PieceColor.BLACK, "P"), 8) is True

    assert piece_rules.is_valid_move("Q", white, Position(2, 2), Position(4, 4), None, 8) is True
    assert piece_rules.is_valid_move("R", white, Position(2, 2), Position(2, 4), None, 8) is True
    assert piece_rules.is_valid_move("B", white, Position(2, 2), Position(4, 4), None, 8) is True
    assert piece_rules.is_valid_move("N", white, Position(2, 2), Position(4, 3), None, 8) is True
    assert piece_rules.is_valid_move("K", white, Position(2, 2), Position(1, 2), None, 8) is True
    with pytest.raises(ValueError):
        piece_rules.is_valid_move("X", white, source, destination, None, 8)

    assert piece_rules.get_path_cells("P", white, Position(6, 0), Position(4, 0)) == [Position(5, 0)]
    assert piece_rules.get_path_cells("Q", white, Position(2, 2), Position(4, 4)) == [Position(3, 3)]
    assert piece_rules.get_path_cells("R", white, Position(2, 2), Position(2, 4)) == [Position(2, 3)]
    assert piece_rules.get_path_cells("B", white, Position(2, 2), Position(4, 4)) == [Position(3, 3)]
    assert piece_rules.get_path_cells("N", white, Position(2, 2), Position(4, 3)) == []
    assert piece_rules.get_path_cells("K", white, Position(2, 2), Position(1, 2)) == []

    fake_board = FakeBoard(
        [[None, None], [None, None]],
        rows=2,
        cols=2,
    )
    with pytest.raises(OutOfBoardError):
        validate_move(fake_board, Position(0, 0), Position(2, 0))

    fake_board = FakeBoard(
        [[None, None], [None, None]],
        rows=2,
        cols=2,
    )
    with pytest.raises(EmptyCellError):
        validate_move(fake_board, Position(0, 0), Position(0, 0))

    piece = Piece(PieceColor.WHITE, "R", cell=Position(0, 0))
    fake_board = FakeBoard(
        [[piece, None], [None, None]],
        rows=2,
        cols=2,
    )
    with pytest.raises(FriendlyFireError):
        validate_move(fake_board, Position(0, 0), Position(0, 0))

    piece.state = PieceState.MOVING
    fake_board = FakeBoard(
        [[piece, None], [None, None]],
        rows=2,
        cols=2,
    )
    with pytest.raises(PieceAlreadyMovingError):
        validate_move(fake_board, Position(0, 0), Position(0, 1))

    piece.state = PieceState.IDLE
    fake_board = FakeBoard(
        [[piece, None], [None, None]],
        rows=2,
        cols=2,
    )
    with pytest.raises(IllegalPatternError):
        validate_move(fake_board, Position(0, 0), Position(1, 1))

    rook = Piece(PieceColor.WHITE, "R", cell=Position(0, 0))
    blocker = Piece(PieceColor.BLACK, "P", cell=Position(0, 1))
    fake_board = FakeBoard(
        [[rook, blocker, None], [None, None, None], [None, None, None]],
        rows=3,
        cols=3,
    )
    with pytest.raises(PathBlockedError):
        validate_move(fake_board, Position(0, 0), Position(0, 2))

    destination_piece = Piece(PieceColor.BLACK, "P", cell=Position(0, 1))
    board = FakeBoard(
        [[rook, destination_piece], [None, None]],
        rows=2,
        cols=2,
    )
    assert validate_move(board, Position(0, 0), Position(0, 1)) == Position(0, 1)


def test_controller_selection_and_move_scheduling(capsys):
    board = make_board(["wR .", ". ."])
    controller = Controller(board)

    controller.handle_click(Position(0, 0))
    assert controller.selected_position == Position(0, 0)

    controller.handle_click(Position(0, 1))
    captured = capsys.readouterr()
    assert "אין כלי בתא המקור" not in captured.out

    controller.handle_click(Position(0, 0))
    controller.handle_click(Position(0, 1))
    assert controller.selected_position is None

    board2 = make_board(["wR .", ". ."])
    controller2 = Controller(board2)
    controller2.handle_click(Position(0, 0))
    controller2.handle_click(Position(0, 0))
    assert controller2.selected_position == Position(0, 0)

    board3 = make_board(["wR bP", ". ."])
    controller3 = Controller(board3)
    controller3.handle_click(Position(0, 0))
    controller3.handle_click(Position(0, 1))
    assert controller3.selected_position is None

    board4 = make_board(["wR .", ". ."])
    controller4 = Controller(board4)
    controller4.handle_click(Position(0, 0))
    controller4.handle_click(Position(1, 0))
    assert controller4.selected_position is None

    board5 = make_board(["wR .", ". ."])
    controller5 = Controller(board5)
    controller5.handle_click(Position(0, 0))
    controller5.handle_click(Position(0, 1))
    assert controller5.selected_position is None

    board6 = make_board(["wR .", ". ."])
    controller6 = Controller(board6)
    controller6.handle_click(Position(0, 0))
    controller6.handle_click(Position(0, 1))
    assert board6._arbiter.has_active_motion(board6.get_piece_at(Position(0, 0))) is True


def test_motion_and_arbiter_arrival_collision_and_promotion():
    motion = Motion(Piece(PieceColor.WHITE, "R"), Position(0, 0), Position(0, 2), 0, 10, 20)
    assert motion.is_arrival_pending(5) is False
    assert motion.is_arrival_pending(10) is True
    assert motion.is_finish_pending(15) is False
    assert motion.is_finish_pending(20) is True
    assert motion.travel_duration() == 10
    motion.bounce(5)
    assert motion.bounced is True
    assert motion.executed is True

    board = make_board(["wR . .", ". . ."])
    piece_a = board.get_piece_at(Position(0, 0))
    piece_b = Piece(PieceColor.BLACK, "R", cell=Position(0, 1))
    board.place_piece(Position(0, 1), piece_b)
    board.schedule_move(Position(0, 0), Position(0, 2), 0, 20)
    board.schedule_move(Position(0, 1), Position(0, 2), 0, 20)

    board.wait(20)
    assert board.get_piece_at(Position(0, 2)).kind == "R"
    assert board.get_piece_at(Position(0, 0)) is None
    assert board._arbiter.consume_royal_capture() is False

    promotion_board = make_board([".", "wP"])
    promotion_board.schedule_move(Position(1, 0), Position(0, 0), 0, 10)
    promotion_board.wait(10)
    assert promotion_board.get_piece_at(Position(0, 0)).kind == "Q"

    royal_board = make_board(["wR . bK", ". . ."])
    royal_board.schedule_move(Position(0, 0), Position(0, 2), 0, 10)
    royal_board.wait(10)
    assert royal_board.consume_royal_capture() is True

    airborne_board = make_board(["wR . bN", ". . ."])
    airborne_piece = airborne_board.get_piece_at(Position(0, 2))
    airborne_piece.start_jump(0)
    airborne_board.schedule_move(Position(0, 0), Position(0, 2), 0, 10)
    airborne_board.wait(10)
    assert airborne_board.get_piece_at(Position(0, 2)) is airborne_piece
    assert airborne_board.get_piece_at(Position(0, 0)) is None


def test_view_renderer_and_game_engine(capsys):
    board = make_board(["wP .", ". bP"])
    game = GameEngine(["wP .", ". bP"])

    game.click(0, 0)
    game.click(100, 0)
    assert game.game_over is False

    game.wait(1000)
    assert game.game_over is False

    game.print_board()
    captured = capsys.readouterr()
    assert "wP ." in captured.out

    assert render_rule_violation(OutOfBoardError("x")) == "The move goes out of bounds"
    assert render_rule_violation(DummyRuleViolation("x")) == "Illegal move: x"

    print_rule_violation(IllegalPatternError("bad"))
    captured = capsys.readouterr()
    assert "The move is illegal for this piece type" in captured.out

    board2 = make_board(["wR . bK", ". . ."])
    game2 = GameEngine(["wR . bK", ". . ."])
    game2.click(0, 0)
    game2.click(200, 0)
    game2.wait(1000)
    assert game2.game_over is True


def test_piece_factory_and_main(monkeypatch, capsys):
    piece = PieceFactory.create_piece("bQ")
    assert piece.color == PieceColor.BLACK
    assert piece.kind == "Q"

    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("wX")

    monkeypatch.setattr(sys, "stdin", io.StringIO("Board:\n.\nCommands:\nclick 0 0\nprint board\n"))
    main_module.main()
    assert "." in capsys.readouterr().out

    monkeypatch.setattr(sys, "stdin", io.StringIO("NoBoardHere\n"))
    main_module.main()
    assert capsys.readouterr().out == ""