import io
import sys
import os
import contextlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from model.position import Position
from model.piece import Piece, PieceColor, PieceState
from model.board import Board
from model.game_state import GameState
from rules.piece_factory import PieceFactory
from rules import piece_rules
from rules.rule_engine import RuleEngine, MoveValidation
from realtime.motion import Motion
from realtime.real_time_arbiter import RealTimeArbiter, ArrivalEvent, ArrivalEvents
from boardio.board_parser import BoardParser
from boardio.board_printer import print_board
from input.board_mapper import BoardMapper
from input.controller import Controller
from engine.game_engine import GameEngine
from view.renderer import render_snapshot, GameSnapshot, PieceSnapshot


# ── helpers ──────────────────────────────────────────────────────────────────

def make_board(lines):
    return BoardParser.parse(lines)


def make_piece(color=PieceColor.WHITE, kind="R", row=0, col=0):
    return Piece(id="p0", color=color, kind=kind, cell=Position(row, col))


# ── Position ─────────────────────────────────────────────────────────────────

def test_position_equality_and_hash():
    assert Position(1, 2) == Position(1, 2)
    assert hash(Position(1, 2)) == hash(Position(1, 2))
    assert Position(1, 2) != Position(2, 1)


# ── Piece ─────────────────────────────────────────────────────────────────────

def test_piece_initial_state():
    p = make_piece()
    assert p.color == PieceColor.WHITE
    assert p.kind == "R"
    assert p.state == PieceState.IDLE
    assert not p.is_moving()


def test_piece_moving_state():
    p = make_piece()
    p.state = PieceState.MOVING
    assert p.is_moving()
    p.state = PieceState.IDLE
    assert not p.is_moving()


def test_piece_str():
    assert str(make_piece(PieceColor.WHITE, "P")) == "wP"
    assert str(make_piece(PieceColor.BLACK, "K")) == "bK"


# ── GameState ─────────────────────────────────────────────────────────────────

def test_gamestate_end_game():
    gs = GameState()
    assert gs.game_over is False
    gs.end_game()
    assert gs.game_over is True


# ── PieceFactory ──────────────────────────────────────────────────────────────

def test_piece_factory_valid_tokens():
    PieceFactory.reset_counter()
    p = PieceFactory.create_piece("wP")
    assert p.color == PieceColor.WHITE
    assert p.kind == "P"
    assert p.id == "piece_0"


def test_piece_factory_with_cell():
    PieceFactory.reset_counter()
    p = PieceFactory.create_piece("bK", cell=Position(3, 4))
    assert p.cell == Position(3, 4)


def test_piece_factory_all_kinds():
    for kind in ("P", "K", "Q", "R", "B", "N"):
        PieceFactory.reset_counter()
        p = PieceFactory.create_piece(f"w{kind}")
        assert p.kind == kind


def test_piece_factory_invalid_token():
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("wX")
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("xP")
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("w")
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        PieceFactory.create_piece("wPP")


def test_piece_factory_counter_increments():
    PieceFactory.reset_counter()
    p1 = PieceFactory.create_piece("wR")
    p2 = PieceFactory.create_piece("bR")
    assert p1.id == "piece_0"
    assert p2.id == "piece_1"


# ── Board ─────────────────────────────────────────────────────────────────────

def test_board_get_piece_at():
    board = make_board(["wR ."])
    assert board.get_piece_at(Position(0, 0)).kind == "R"
    assert board.get_piece_at(Position(0, 1)) is None


def test_board_is_inside():
    board = make_board(["wR ."])
    assert board.is_inside_board(Position(0, 0))
    assert not board.is_inside_board(Position(1, 0))
    assert not board.is_inside_board(Position(0, 2))


def test_board_get_piece_outside_raises():
    board = make_board(["wR ."])
    with pytest.raises(ValueError):
        board.get_piece_at(Position(5, 5))


def test_board_place_and_remove():
    board = make_board([". ."])
    p = make_piece(row=0, col=1)
    board.place_piece(Position(0, 1), p)
    assert board.get_piece_at(Position(0, 1)) is p
    board.remove_piece(Position(0, 1))
    assert board.get_piece_at(Position(0, 1)) is None


def test_board_place_occupied_raises():
    board = make_board(["wR ."])
    p = make_piece()
    with pytest.raises(ValueError):
        board.place_piece(Position(0, 0), p)


def test_board_move_piece_no_capture():
    board = make_board(["wR ."])
    captured = board.move_piece(Position(0, 0), Position(0, 1))
    assert captured is None
    assert board.get_piece_at(Position(0, 1)).kind == "R"
    assert board.get_piece_at(Position(0, 0)) is None


def test_board_move_piece_with_capture():
    board = make_board(["wR bP"])
    captured = board.move_piece(Position(0, 0), Position(0, 1))
    assert captured is not None
    assert captured.kind == "P"
    assert board.get_piece_at(Position(0, 1)).kind == "R"


def test_board_move_piece_no_source_raises():
    board = make_board([". ."])
    with pytest.raises(ValueError):
        board.move_piece(Position(0, 0), Position(0, 1))


def test_board_get_grid():
    board = make_board(["wR ."])
    grid = board.get_grid()
    assert grid[0][0].kind == "R"


# ── BoardParser ───────────────────────────────────────────────────────────────

def test_board_parser_basic():
    board = make_board(["wP .", ". bK"])
    assert board.rows == 2
    assert board.cols == 2
    assert board.get_piece_at(Position(0, 0)).kind == "P"
    assert board.get_piece_at(Position(1, 1)).kind == "K"
    assert board.get_piece_at(Position(0, 1)) is None


def test_board_parser_row_width_mismatch():
    with pytest.raises(ValueError, match="ROW_WIDTH_MISMATCH"):
        BoardParser.parse(["wP .", "."])


def test_board_parser_unknown_token():
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        BoardParser.parse(["wX"])


# ── BoardPrinter ──────────────────────────────────────────────────────────────

def test_board_printer_output():
    board = make_board(["wP .", ". bK"])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        print_board(board.get_grid())
    lines = out.getvalue().strip().splitlines()
    assert lines[0] == "wP ."
    assert lines[1] == ". bK"


# ── BoardMapper ───────────────────────────────────────────────────────────────

def test_board_mapper_pixel_to_position():
    mapper = BoardMapper(4, 4, cell_size=100)
    assert mapper.pixel_to_position(0, 0) == Position(0, 0)
    assert mapper.pixel_to_position(250, 150) == Position(1, 2)


def test_board_mapper_is_inside():
    mapper = BoardMapper(2, 3, cell_size=100)
    assert mapper.is_inside_board(Position(1, 2))
    assert not mapper.is_inside_board(Position(2, 0))
    assert not mapper.is_inside_board(Position(0, 3))


def test_board_mapper_update_dimensions():
    mapper = BoardMapper(2, 2)
    mapper.update_dimensions(4, 5)
    assert mapper.rows == 4
    assert mapper.cols == 5


# ── piece_rules ───────────────────────────────────────────────────────────────

def test_piece_rules_timing():
    assert piece_rules.get_move_time("R") == 1000
    assert piece_rules.get_arrival_duration("R", Position(0, 0), Position(0, 3)) == 3000
    assert piece_rules.get_arrival_duration("N", Position(0, 0), Position(2, 1)) == 3000


def test_piece_rules_is_royal():
    assert piece_rules.is_royal("K")
    assert not piece_rules.is_royal("Q")


def test_piece_rules_pawn_forward():
    assert piece_rules.is_valid_move("P", PieceColor.WHITE, Position(6, 0), Position(5, 0), None, 8)
    assert not piece_rules.is_valid_move("P", PieceColor.WHITE, Position(6, 0), Position(7, 0), None, 8)


def test_piece_rules_pawn_double_opening():
    assert piece_rules.is_valid_move("P", PieceColor.WHITE, Position(6, 0), Position(4, 0), None, 8)
    assert piece_rules.is_valid_move("P", PieceColor.BLACK, Position(1, 0), Position(3, 0), None, 8)
    assert not piece_rules.is_valid_move("P", PieceColor.WHITE, Position(5, 0), Position(3, 0), None, 8)


def test_piece_rules_pawn_capture():
    enemy = make_piece(PieceColor.BLACK, "P")
    assert piece_rules.is_valid_move("P", PieceColor.WHITE, Position(6, 1), Position(5, 0), enemy, 8)
    assert not piece_rules.is_valid_move("P", PieceColor.WHITE, Position(6, 1), Position(5, 0), None, 8)


def test_piece_rules_queen():
    assert piece_rules.is_valid_move("Q", PieceColor.WHITE, Position(0, 0), Position(3, 3), None, 8)
    assert piece_rules.is_valid_move("Q", PieceColor.WHITE, Position(0, 0), Position(0, 5), None, 8)
    assert not piece_rules.is_valid_move("Q", PieceColor.WHITE, Position(0, 0), Position(1, 2), None, 8)


def test_piece_rules_rook():
    assert piece_rules.is_valid_move("R", PieceColor.WHITE, Position(0, 0), Position(0, 4), None, 8)
    assert not piece_rules.is_valid_move("R", PieceColor.WHITE, Position(0, 0), Position(1, 1), None, 8)


def test_piece_rules_bishop():
    assert piece_rules.is_valid_move("B", PieceColor.WHITE, Position(0, 0), Position(3, 3), None, 8)
    assert not piece_rules.is_valid_move("B", PieceColor.WHITE, Position(0, 0), Position(0, 3), None, 8)


def test_piece_rules_knight():
    assert piece_rules.is_valid_move("N", PieceColor.WHITE, Position(0, 0), Position(2, 1), None, 8)
    assert not piece_rules.is_valid_move("N", PieceColor.WHITE, Position(0, 0), Position(2, 2), None, 8)


def test_piece_rules_king():
    assert piece_rules.is_valid_move("K", PieceColor.WHITE, Position(4, 4), Position(4, 5), None, 8)
    assert not piece_rules.is_valid_move("K", PieceColor.WHITE, Position(4, 4), Position(4, 6), None, 8)


def test_piece_rules_unknown_kind():
    with pytest.raises(ValueError):
        piece_rules.is_valid_move("X", PieceColor.WHITE, Position(0, 0), Position(1, 1), None, 8)


def test_piece_rules_pathcells_pawn_single():
    assert piece_rules.get_pathcells("P", PieceColor.WHITE, Position(5, 0), Position(4, 0)) == []


def test_piece_rules_pathcells_pawn_double():
    assert piece_rules.get_pathcells("P", PieceColor.WHITE, Position(6, 0), Position(4, 0)) == [Position(5, 0)]


def test_piece_rules_pathcells_queen_diagonal():
    assert piece_rules.get_pathcells("Q", PieceColor.WHITE, Position(0, 0), Position(3, 3)) == [
        Position(1, 1), Position(2, 2)
    ]


def test_piece_rules_pathcells_rook():
    assert piece_rules.get_pathcells("R", PieceColor.WHITE, Position(0, 0), Position(0, 3)) == [
        Position(0, 1), Position(0, 2)
    ]


def test_piece_rules_pathcells_bishop():
    assert piece_rules.get_pathcells("B", PieceColor.WHITE, Position(0, 0), Position(2, 2)) == [Position(1, 1)]


def test_piece_rules_pathcells_knight_and_king():
    assert piece_rules.get_pathcells("N", PieceColor.WHITE, Position(0, 0), Position(2, 1)) == []
    assert piece_rules.get_pathcells("K", PieceColor.WHITE, Position(0, 0), Position(1, 1)) == []


# ── RuleEngine ────────────────────────────────────────────────────────────────

def test_rule_engine_ok():
    board = make_board(["wR . ."])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(0, 2))
    assert result.is_valid
    assert result.reason == "ok"


def test_rule_engine_outside_board():
    board = make_board(["wR ."])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(5, 5))
    assert not result.is_valid
    assert result.reason == "outside_board"


def test_rule_engine_empty_source():
    board = make_board([". ."])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(0, 1))
    assert not result.is_valid
    assert result.reason == "empty_source"


def test_rule_engine_friendly_destination():
    board = make_board(["wR wP"])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(0, 1))
    assert not result.is_valid
    assert result.reason == "friendly_destination"


def test_rule_engine_illegal_piece_move():
    board = make_board(["wR . .", ". . .", ". . ."])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(1, 1))
    assert not result.is_valid
    assert result.reason == "illegal_piece_move"


def test_rule_engine_path_blocked():
    board = make_board(["wR bP ."])
    result = RuleEngine.validate_move(board, Position(0, 0), Position(0, 2))
    assert not result.is_valid
    assert result.reason == "illegal_piece_move"


# ── Motion ────────────────────────────────────────────────────────────────────

def test_motion_arrival_pending():
    p = make_piece()
    m = Motion(p, Position(0, 0), Position(0, 2), start_time=0, arrival_time=2000)
    assert not m.is_arrival_pending(1000)
    assert m.is_arrival_pending(2000)
    assert m.is_arrival_pending(3000)


# ── RealTimeArbiter ───────────────────────────────────────────────────────────

def test_arbiter_start_and_has_motion():
    board = make_board(["wR . ."])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    assert not arbiter.has_active_motion(piece)
    arbiter.start_motion(piece, Position(0, 0), Position(0, 2))
    assert arbiter.has_active_motion(piece)
    assert piece.state == PieceState.MOVING


def test_arbiter_advance_time_arrival():
    board = make_board(["wR . ."])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(piece, Position(0, 0), Position(0, 2))
    events = arbiter.advance_time(2000)
    assert len(events.events) == 1
    assert board.get_piece_at(Position(0, 2)) is piece
    assert board.get_piece_at(Position(0, 0)) is None
    # Arrival starts a LONG_REST cooldown rather than going straight to IDLE.
    assert piece.state == PieceState.LONG_REST
    arbiter.advance_time(piece_rules.get_long_rest_duration())
    assert piece.state == PieceState.IDLE


def test_arbiter_no_arrival_before_time():
    board = make_board(["wR . ."])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(piece, Position(0, 0), Position(0, 2))
    events = arbiter.advance_time(500)
    assert len(events.events) == 0
    assert board.get_piece_at(Position(0, 0)) is piece


def test_arbiter_king_capture():
    board = make_board(["wR bK"])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(piece, Position(0, 0), Position(0, 1))
    events = arbiter.advance_time(1000)
    assert events.king_captured is True


def test_arbiter_consume_royal_capture_resets():
    board = make_board(["wR bK"])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(piece, Position(0, 0), Position(0, 1))
    arbiter.advance_time(1000)
    assert not arbiter.consume_royal_capture()


def test_arbiter_collision_first_scheduled_wins():
    board = make_board(["wR . bR"])
    arbiter = RealTimeArbiter(board)
    white = board.get_piece_at(Position(0, 0))
    black = board.get_piece_at(Position(0, 2))
    arbiter.start_motion(white, Position(0, 0), Position(0, 2))
    arbiter.start_motion(black, Position(0, 2), Position(0, 0))
    arbiter.advance_time(2000)
    assert board.get_piece_at(Position(0, 2)) is white
    assert black.state == PieceState.CAPTURED


def test_arbiter_captured_piece_arrival_skipped():
    board = make_board(["wR bR ."])
    arbiter = RealTimeArbiter(board)
    white = board.get_piece_at(Position(0, 0))
    black = board.get_piece_at(Position(0, 1))
    arbiter.start_motion(white, Position(0, 0), Position(0, 1))
    arbiter.start_motion(black, Position(0, 1), Position(0, 2))
    arbiter.advance_time(1000)
    # white arrives at (0,1) and captures black; black's motion is dropped
    assert board.get_piece_at(Position(0, 1)) is white
    assert board.get_piece_at(Position(0, 2)) is None


def test_arbiter_friendly_destination_stops_one_cell_short():
    board = make_board(["wR . . .", ". . . wR"])
    arbiter = RealTimeArbiter(board)
    mover = board.get_piece_at(Position(0, 0))
    blocker = board.get_piece_at(Position(1, 3))
    arbiter.start_motion(mover, Position(0, 0), Position(0, 3))
    arbiter.start_motion(blocker, Position(1, 3), Position(0, 3))
    arbiter.advance_time(1000)
    # blocker arrives first and settles onto the mover's destination
    assert board.get_piece_at(Position(0, 3)) is blocker
    arbiter.advance_time(2000)
    # mover stops one cell short instead of capturing its own blocker
    assert board.get_piece_at(Position(0, 2)) is mover
    assert board.get_piece_at(Position(0, 0)) is None
    assert board.get_piece_at(Position(0, 3)) is blocker
    assert mover.state == PieceState.LONG_REST


def test_arbiter_friendly_destination_dropped_when_stop_cell_also_blocked():
    board = make_board(["wR . wR wR"])
    arbiter = RealTimeArbiter(board)
    mover = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(mover, Position(0, 0), Position(0, 3))
    arbiter.advance_time(3000)
    # both the destination and the cell before it are occupied by friendlies
    # -- the move is dropped entirely and the mover stays put
    assert board.get_piece_at(Position(0, 0)) is mover
    assert board.get_piece_at(Position(0, 2)) is not None
    assert board.get_piece_at(Position(0, 3)) is not None
    assert mover.state == PieceState.IDLE


def test_arbiter_friendly_destination_dropped_on_adjacent_move():
    board = make_board(["wR wR"])
    arbiter = RealTimeArbiter(board)
    mover = board.get_piece_at(Position(0, 0))
    arbiter.start_motion(mover, Position(0, 0), Position(0, 1))
    arbiter.advance_time(1000)
    # no intermediate cell to stop at (adjacent move) -- move is dropped
    assert board.get_piece_at(Position(0, 0)) is mover
    assert board.get_piece_at(Position(0, 1)) is not None
    assert mover.state == PieceState.IDLE


# ── Controller ────────────────────────────────────────────────────────────────

def _make_controller(lines):
    board = make_board(lines)
    engine = GameEngine(board)
    mapper = BoardMapper(board.rows, board.cols)
    return Controller(board, engine, mapper), board, engine


def test_controller_select_piece():
    ctrl, board, _ = _make_controller(["wR ."])
    ctrl.handle_click(Position(0, 0))
    assert ctrl.selected_position == Position(0, 0)


def test_controller_click_empty_no_select():
    ctrl, _, _ = _make_controller([". ."])
    ctrl.handle_click(Position(0, 0))
    assert ctrl.selected_position is None


def test_controller_move_clears_selection():
    ctrl, _, _ = _make_controller(["wR . ."])
    ctrl.handle_click(Position(0, 0))
    ctrl.handle_click(Position(0, 2))
    assert ctrl.selected_position is None


def test_controller_friendly_click_switches_selection():
    ctrl, _, _ = _make_controller(["wR wP"])
    ctrl.handle_click(Position(0, 0))
    ctrl.handle_click(Position(0, 1))
    assert ctrl.selected_position == Position(0, 1)


def test_controller_pixel_click_inside():
    ctrl, _, _ = _make_controller(["wR . ."])
    ctrl.handle_pixel_click(0, 0)
    assert ctrl.selected_position == Position(0, 0)


def test_controller_pixel_click_outside_cancels_selection():
    ctrl, _, _ = _make_controller(["wR ."])
    ctrl.handle_click(Position(0, 0))
    ctrl.handle_pixel_click(9999, 9999)
    assert ctrl.selected_position is None


def test_controller_pixel_click_outside_no_selection_ignored():
    ctrl, _, _ = _make_controller(["wR ."])
    ctrl.handle_pixel_click(9999, 9999)
    assert ctrl.selected_position is None


# ── GameEngine ────────────────────────────────────────────────────────────────

def test_game_engine_request_move_ok():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    result = engine.request_move(Position(0, 0), Position(0, 2))
    assert result.is_accepted
    assert result.reason == "ok"


def test_game_engine_request_move_invalid():
    board = make_board(["wR . .", ". . .", ". . ."])
    engine = GameEngine(board)
    result = engine.request_move(Position(0, 0), Position(1, 1))
    assert not result.is_accepted
    assert result.reason == "illegal_piece_move"


def test_game_engine_motion_in_progress():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 2))
    result = engine.request_move(Position(0, 0), Position(0, 1))
    assert not result.is_accepted
    assert result.reason == "motion_in_progress"


def test_game_engine_game_over_blocks_moves():
    board = make_board(["wR bK"])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 1))
    engine.wait(1000)
    assert engine.game_over
    result = engine.request_move(Position(0, 1), Position(0, 0))
    assert not result.is_accepted
    assert result.reason == "game_over"


def test_game_engine_wait_advances_time():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 2))
    engine.wait(2000)
    assert board.get_piece_at(Position(0, 2)) is not None


def test_game_engine_snapshot():
    board = make_board(["wR ."])
    engine = GameEngine(board)
    snap = engine.snapshot()
    assert snap.board_width == 2
    assert snap.board_height == 1
    assert len(snap.pieces) == 1
    assert snap.pieces[0].kind == "R"
    assert snap.game_over is False


def test_game_engine_snapshot_with_selected_cell():
    board = make_board(["wR ."])
    engine = GameEngine(board)
    snap = engine.snapshot(selected_cell=Position(0, 0))
    assert snap.selected_cell == Position(0, 0)


def test_game_engine_snapshot_excludes_captured():
    board = make_board(["wR bK"])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 1))
    engine.wait(1000)
    snap = engine.snapshot()
    kinds = [p.kind for p in snap.pieces]
    assert "K" not in kinds


# ── Renderer ──────────────────────────────────────────────────────────────────

def test_render_snapshot_output():
    snap = GameSnapshot(
        board_width=2,
        board_height=2,
        pieces=[
            PieceSnapshot(id="p1", kind="R", color="w", cell=Position(0, 0), state="IDLE"),
            PieceSnapshot(id="p2", kind="K", color="b", cell=Position(1, 1), state="IDLE"),
        ],
        selected_cell=None,
        game_over=False,
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        render_snapshot(snap)
    lines = out.getvalue().strip().splitlines()
    assert lines[0] == "wR ."
    assert lines[1] == ". bK"


def test_render_snapshot_empty_board():
    snap = GameSnapshot(
        board_width=2, board_height=1, pieces=[], selected_cell=None, game_over=False
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        render_snapshot(snap)
    assert out.getvalue().strip() == ". ."


def test_piece_rules_queen_pathcells_straight():
    # covers queen path along a row (col_step != 0, row_step == 0)
    assert piece_rules.get_pathcells("Q", PieceColor.WHITE, Position(0, 0), Position(0, 3)) == [
        Position(0, 1), Position(0, 2)
    ]


def test_piece_rules_rook_pathcells_upward():
    # covers rook path going upward (destination.row < source.row)
    assert piece_rules.get_pathcells("R", PieceColor.WHITE, Position(3, 0), Position(0, 0)) == [
        Position(2, 0), Position(1, 0)
    ]


def test_piece_rules_rook_pathcells_leftward():
    # covers rook path going left (destination.col < source.col)
    assert piece_rules.get_pathcells("R", PieceColor.WHITE, Position(0, 3), Position(0, 0)) == [
        Position(0, 2), Position(0, 1)
    ]


# ── Piece: airborne / resting ──────────────────────────────────────────────────

def test_piece_is_airborne():
    p = make_piece()
    assert not p.is_airborne()
    p.state = PieceState.AIRBORNE
    assert p.is_airborne()


def test_piece_is_resting():
    p = make_piece()
    assert not p.is_resting()
    p.state = PieceState.LONG_REST
    assert p.is_resting()
    p.state = PieceState.SHORT_REST
    assert p.is_resting()


# ── piece_rules: promotion / short rest ─────────────────────────────────────────

def test_piece_rules_promotion_white_back_rank():
    assert piece_rules.get_promotion_kind("P", PieceColor.WHITE, Position(0, 3), 8) == "Q"


def test_piece_rules_promotion_black_back_rank():
    assert piece_rules.get_promotion_kind("P", PieceColor.BLACK, Position(7, 3), 8) == "Q"


def test_piece_rules_no_promotion_mid_board():
    assert piece_rules.get_promotion_kind("P", PieceColor.WHITE, Position(3, 3), 8) is None


def test_piece_rules_no_promotion_non_pawn():
    assert piece_rules.get_promotion_kind("Q", PieceColor.WHITE, Position(0, 3), 8) is None


def test_piece_rules_short_rest_duration():
    assert piece_rules.get_short_rest_duration() == 1000


# ── RealTimeArbiter: jump / landing / resting / airborne capture / promotion ───

def test_arbiter_start_jump_sets_airborne():
    board = make_board(["wN ."])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_jump(piece)
    assert piece.is_airborne()


def test_arbiter_jump_lands_into_short_rest_then_idle():
    board = make_board(["wN ."])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(0, 0))
    arbiter.start_jump(piece)
    arbiter.advance_time(piece_rules.get_airborne_duration())
    assert piece.state == PieceState.SHORT_REST
    arbiter.advance_time(piece_rules.get_short_rest_duration())
    assert piece.state == PieceState.IDLE


def test_arbiter_airborne_capture_of_arriving_piece():
    board = make_board(["wR bN"])
    arbiter = RealTimeArbiter(board)
    white = board.get_piece_at(Position(0, 0))
    black_jumper = board.get_piece_at(Position(0, 1))
    arbiter.start_jump(black_jumper)
    arbiter.start_motion(white, Position(0, 0), Position(0, 1))
    events = arbiter.advance_time(1000)
    assert white.state == PieceState.CAPTURED
    assert board.get_piece_at(Position(0, 1)) is black_jumper
    assert board.get_piece_at(Position(0, 0)) is None
    assert len(events.events) == 1


def test_arbiter_airborne_capture_of_king_ends_game():
    board = make_board(["wK bN"])
    arbiter = RealTimeArbiter(board)
    king = board.get_piece_at(Position(0, 0))
    black_jumper = board.get_piece_at(Position(0, 1))
    arbiter.start_jump(black_jumper)
    arbiter.start_motion(king, Position(0, 0), Position(0, 1))
    events = arbiter.advance_time(1000)
    assert events.king_captured is True


def test_arbiter_pawn_promotion_on_arrival():
    board = make_board([".", "wP"])
    arbiter = RealTimeArbiter(board)
    piece = board.get_piece_at(Position(1, 0))
    arbiter.start_motion(piece, Position(1, 0), Position(0, 0))
    arbiter.advance_time(1000)
    assert board.get_piece_at(Position(0, 0)).kind == "Q"


# ── GameEngine: request_jump ────────────────────────────────────────────────────

def test_game_engine_request_jump_starts_jump():
    board = make_board(["wN ."])
    engine = GameEngine(board)
    piece = board.get_piece_at(Position(0, 0))
    engine.request_jump(Position(0, 0))
    assert piece.is_airborne()


def test_game_engine_request_jump_game_over_ignored():
    board = make_board(["wR bK"])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 1))
    engine.wait(1000)
    assert engine.game_over
    engine.request_jump(Position(0, 1))  # no-op, must not raise


def test_game_engine_request_jump_empty_source_ignored():
    board = make_board([". ."])
    engine = GameEngine(board)
    engine.request_jump(Position(0, 0))  # no-op, must not raise


def test_game_engine_request_jump_moving_piece_ignored():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 2))
    piece = board.get_piece_at(Position(0, 0))
    engine.request_jump(Position(0, 0))
    assert not piece.is_airborne()


def test_game_engine_request_jump_resting_piece_ignored():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 2))
    engine.wait(2000)
    piece = board.get_piece_at(Position(0, 2))
    assert piece.is_resting()
    engine.request_jump(Position(0, 2))
    assert not piece.is_airborne()


def test_game_engine_request_jump_captured_piece_ignored():
    board = make_board(["wR ."])
    engine = GameEngine(board)
    piece = board.get_piece_at(Position(0, 0))
    piece.state = PieceState.CAPTURED
    engine.request_jump(Position(0, 0))
    assert not piece.is_airborne()


# ── GameEngine: request_move resting guard ──────────────────────────────────────

def test_game_engine_request_move_resting_blocked():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    engine.request_move(Position(0, 0), Position(0, 2))
    engine.wait(2000)
    result = engine.request_move(Position(0, 2), Position(0, 1))
    assert not result.is_accepted
    assert result.reason == "resting"


# ── GameEngine: observer notifications ──────────────────────────────────────────

class _RecordingObserver:
    def __init__(self):
        self.motion_started = []
        self.jump_started = []
        self.arrivals = []
        self.game_over_calls = 0

    def on_motion_started(self, piece, source, destination, duration_ms):
        self.motion_started.append((piece, source, destination, duration_ms))

    def on_jump_started(self, piece, position):
        self.jump_started.append((piece, position))

    def on_arrival(self, event):
        self.arrivals.append(event)

    def on_game_over(self):
        self.game_over_calls += 1


def test_game_engine_subscribe_receives_motion_started():
    board = make_board(["wR . ."])
    engine = GameEngine(board)
    observer = _RecordingObserver()
    engine.subscribe(observer)
    engine.request_move(Position(0, 0), Position(0, 2))
    assert len(observer.motion_started) == 1
    _, source, destination, duration_ms = observer.motion_started[0]
    assert source == Position(0, 0)
    assert destination == Position(0, 2)
    assert duration_ms == 2000


def test_game_engine_subscribe_receives_jump_started():
    board = make_board(["wN ."])
    engine = GameEngine(board)
    observer = _RecordingObserver()
    engine.subscribe(observer)
    engine.request_jump(Position(0, 0))
    assert len(observer.jump_started) == 1
    _, position = observer.jump_started[0]
    assert position == Position(0, 0)


def test_game_engine_subscribe_receives_arrival_and_game_over():
    board = make_board(["wR bK"])
    engine = GameEngine(board)
    observer = _RecordingObserver()
    engine.subscribe(observer)
    engine.request_move(Position(0, 0), Position(0, 1))
    engine.wait(1000)
    assert len(observer.arrivals) == 1
    assert observer.game_over_calls == 1


def test_game_engine_unsubscribe_stops_all_observer_notifications():
    board = make_board(["wR . .", ". . bK"])
    engine = GameEngine(board)
    observer = _RecordingObserver()
    unsubscribe = engine.subscribe(observer)

    unsubscribe()
    unsubscribe()

    engine.request_move(Position(0, 0), Position(0, 2))
    engine.wait(2000)
    engine.request_jump(Position(1, 2))

    assert observer.motion_started == []
    assert observer.jump_started == []
    assert observer.arrivals == []
    assert observer.game_over_calls == 0
