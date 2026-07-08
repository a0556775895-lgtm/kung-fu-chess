import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from board import Board
from pawn import Pawn
from queen import Queen


def test_board_size():
    board = Board([
        ". . .",
        ". . .",
    ])

    assert board.get_rows() == 2
    assert board._cols == 3


def test_empty_cells():
    board = Board([
        ". .",
        ". .",
    ])

    assert board._grid[0][0] is None
    assert board._grid[1][1] is None


def test_piece_creation():
    board = Board([
        "wP .",
        ". bP",
    ])

    assert isinstance(board._grid[0][0], Pawn)
    assert isinstance(board._grid[1][1], Pawn)


def test_piece_board_reference():
    board = Board([
        "wP",
    ])

    piece = board._grid[0][0]

    assert piece.get_board() is board


def test_row_width_mismatch():
    with pytest.raises(ValueError, match="ROW_WIDTH_MISMATCH"):
        Board([
            ". . .",
            ". .",
        ])


def test_unknown_token():
    with pytest.raises(ValueError, match="UNKNOWN_TOKEN"):
        Board([
            "wX",
        ])


def test_pixel_to_cell():
    board = Board([
        ". .",
        ". .",
    ])

    assert board._pixel_to_cell(250, 150) == (1, 2)


def test_inside_board():
    board = Board([
        ". .",
        ". .",
    ])

    assert board._is_inside_board(0, 0)
    assert board._is_inside_board(1, 1)


def test_outside_board():
    board = Board([
        ". .",
        ". .",
    ])

    assert not board._is_inside_board(-1, 0)
    assert not board._is_inside_board(0, -1)
    assert not board._is_inside_board(2, 0)
    assert not board._is_inside_board(0, 2)

    def test_click_game_over():
        board = Board([
            "wP .",
            ". .",
        ])

    board._game_over = True

    board.click(0, 0)

    assert board._selected_position is None


def test_click_while_move_pending():
    board = Board([
        "wP .",
        ". .",
    ])

    board._pending_finish_time = 1000

    board.click(0, 0)

    assert board._selected_position is None


def test_click_outside_board():
    board = Board([
        "wP .",
        ". .",
    ])

    board.click(-100, 0)

    assert board._selected_position is None


def test_select_piece():
    board = Board([
        "wP .",
        ". .",
    ])

    board.click(0, 0)

    assert board._selected_position == (0, 0)


def test_click_empty_cell_without_selection():
    board = Board([
        ". .",
        ". .",
    ])

    board.click(0, 0)

    assert board._selected_position is None


def test_replace_selection_with_same_color_piece():
    board = Board([
        "wR wP",
        ". .",
    ])

    board.click(0, 0)
    board.click(100, 0)

    assert board._selected_position == (0, 1)


def test_illegal_move_clears_selection():
    board = Board([
        "wR .",
        ". .",
    ])

    board.click(0, 0)
    board.click(100, 100)

    assert board._selected_position is None


def test_blocked_path_clears_selection():
    board = Board([
        "wR wP .",
    ])

    board.click(0, 0)
    board.click(200, 0)

    assert board._selected_position is None


def test_legal_move_creates_pending_move():
    board = Board([
        "wR . .",
    ])

    board.click(0, 0)
    board.click(200, 0)

    assert board._pending_source == (0, 0)
    assert board._pending_destination == (0, 2)
    assert board._pending_arrival_time == 1000
    assert board._pending_finish_time == 2000

def test_wait_without_pending_move():
    board = Board([
        "wR .",
    ])

    board.wait(1000)

    assert board._pending_source is None
    assert board._pending_destination is None


def test_wait_before_arrival():
    board = Board([
        "wR . .",
    ])

    board.click(0, 0)
    board.click(200, 0)

    board.wait(500)

    assert board._grid[0][0] is not None
    assert board._grid[0][2] is None


def test_wait_after_arrival():
    board = Board([
        "wR . .",
    ])

    board.click(0, 0)
    board.click(200, 0)

    board.wait(1000)

    assert board._grid[0][0] is None
    assert board._grid[0][2] is not None


def test_wait_after_finish():
    board = Board([
        "wR . .",
    ])

    board.click(0, 0)
    board.click(200, 0)

    board.wait(2000)

    assert board._pending_source is None
    assert board._pending_destination is None
    assert board._pending_arrival_time is None
    assert board._pending_finish_time is None


def test_wait_capture_piece():
    board = Board([
        "wR . bP",
    ])

    board.click(0, 0)
    board.click(200, 0)

    board.wait(1000)

    assert board._grid[0][2].color == "w"
    assert board._grid[0][0] is None


def test_jump_game_over():
    board = Board([
        "wN .",
    ])

    board._game_over = True

    board.jump(0, 0)

    piece = board._grid[0][0]
    assert not piece.is_airborne()


def test_jump_outside_board():
    board = Board([
        "wN .",
    ])

    board.jump(-100, 0)

    piece = board._grid[0][0]
    assert not piece.is_airborne()


def test_jump_empty_cell():
    board = Board([
        ". .",
    ])

    board.jump(0, 0)

    assert True


def test_jump_pending_source():
    board = Board([
        "wN . .",
    ])

    board._pending_source = (0, 0)

    board.jump(0, 0)

    piece = board._grid[0][0]
    assert not piece.is_airborne()


def test_jump_success():
    board = Board([
        "wN .",
    ])

    board.jump(0, 0)

    piece = board._grid[0][0]
    assert piece.is_airborne()


def test_jump_airborne_piece():
    board = Board([
        "wN .",
    ])

    piece = board._grid[0][0]
    piece.start_jump(0)

    board.jump(0, 0)

    assert piece.is_airborne()


def test_capture_king_ends_game():
    board = Board([
        "wR . bK",
    ])

    board.click(0, 0)
    board.click(200, 0)

    board.wait(1000)

    assert board._game_over



def test_white_pawn_promotion():
    board = Board([
        ".",
        "wP",
    ])

    board.click(0, 100)
    board.click(0, 0)

    board.wait(1000)

    assert isinstance(board._grid[0][0], Queen)

def test_black_pawn_promotion():
    board = Board([
        "bP",
        ".",
    ])

    board.click(0, 0)
    board.click(0, 100)

    board.wait(1000)

    assert isinstance(board._grid[1][0], Queen)

def test_capture_airborne_piece():
    board = Board([
        "wR . bN",
    ])

    enemy = board._grid[0][2]
    enemy.start_jump(0)

    board.click(0, 0)
    board.click(200, 0)

    board.wait(1000)

    assert board._grid[0][0] is None
    assert board._grid[0][2] is enemy

def test_click_after_game_over():
    board = Board([
        "wR",
    ])

    board._game_over = True

    board.click(0, 0)

    assert board._selected_position is None

def test_jump_outside():
    board = Board([
        "wN",
    ])

    piece = board._grid[0][0]

    board.jump(-1, -1)

    assert not piece.is_airborne()

def test_print_board(capsys):
    board = Board([
        "wP .",
        ". bP",
    ])

    board.print_board()

    captured = capsys.readouterr()

    assert captured.out == "wP .\n. bP\n"