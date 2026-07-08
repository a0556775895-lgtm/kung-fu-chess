import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest

from piece import Piece, PieceColor


class DummyPiece(Piece):
    def __init__(self):
        super().__init__(PieceColor.WHITE, "X", 1500)

    def is_valid_move(
        self,
        source_row,
        source_col,
        destination_row,
        destination_col,
        destination_piece,
    ):
        return True


class DummyBoard:
    def get_rows(self):
        return 8


def test_constructor():
    piece = DummyPiece()

    assert piece.color == PieceColor.WHITE
    assert piece.symbol == "X"
    assert piece.move_time == 1500
    assert piece.get_board() is None
    assert piece.is_airborne() is False


def test_string_representation():
    piece = DummyPiece()

    assert str(piece) == "wX"


def test_set_board():
    piece = DummyPiece()
    board = DummyBoard()

    piece.set_board(board)

    assert piece.get_board() is board


def test_default_path_cells():
    piece = DummyPiece()

    assert piece.get_path_cells(0, 0, 5, 5) == []


def test_start_jump():
    piece = DummyPiece()

    piece.start_jump(100)

    assert piece.is_airborne() is True


def test_finish_jump():
    piece = DummyPiece()

    piece.start_jump(100)
    piece.finish_jump()

    assert piece.is_airborne() is False
    assert piece._jump_finish_time is None


def test_should_finish_jump_before_time():
    piece = DummyPiece()

    piece.start_jump(100)

    assert piece.should_finish_jump(500) is False


def test_should_finish_jump_exact_time():
    piece = DummyPiece()

    piece.start_jump(100)

    assert piece.should_finish_jump(1100) is True


def test_should_finish_jump_after_time():
    piece = DummyPiece()

    piece.start_jump(100)

    assert piece.should_finish_jump(1300) is True


def test_should_finish_jump_when_not_airborne():
    piece = DummyPiece()

    assert piece.should_finish_jump(5000) is False