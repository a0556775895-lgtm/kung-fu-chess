import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pawn import Pawn


class DummyBoard:
    def __init__(self, rows=8):
        self._rows = rows

    def get_rows(self):
        return self._rows


class DummyPiece:
    def __init__(self, color):
        self.color = color


def test_constructor():
    pawn = Pawn("w")

    assert pawn.color == "w"
    assert pawn.symbol == "P"
    assert pawn.move_time == 1000


def test_white_one_step_forward():
    pawn = Pawn("w")
    pawn.set_board(DummyBoard())

    assert pawn.is_valid_move(7, 3, 6, 3, None)


def test_white_two_steps_from_start():
    pawn = Pawn("w")
    pawn.set_board(DummyBoard())

    assert pawn.is_valid_move(7, 3, 5, 3, None)


def test_white_two_steps_not_from_start():
    pawn = Pawn("w")
    pawn.set_board(DummyBoard())

    assert not pawn.is_valid_move(6, 3, 4, 3, None)


def test_black_one_step_forward():
    pawn = Pawn("b")
    pawn.set_board(DummyBoard())

    assert pawn.is_valid_move(0, 3, 1, 3, None)


def test_black_two_steps_from_start():
    pawn = Pawn("b")
    pawn.set_board(DummyBoard())

    assert pawn.is_valid_move(0, 3, 2, 3, None)


def test_black_two_steps_not_from_start():
    pawn = Pawn("b")
    pawn.set_board(DummyBoard())

    assert not pawn.is_valid_move(1, 3, 3, 3, None)


def test_white_capture():
    pawn = Pawn("w")

    enemy = DummyPiece("b")

    assert pawn.is_valid_move(
        5,
        3,
        4,
        4,
        enemy,
    )


def test_black_capture():
    pawn = Pawn("b")

    enemy = DummyPiece("w")

    assert pawn.is_valid_move(
        2,
        3,
        3,
        2,
        enemy,
    )


def test_cannot_capture_same_color():
    pawn = Pawn("w")

    friend = DummyPiece("w")

    assert not pawn.is_valid_move(
        5,
        3,
        4,
        4,
        friend,
    )


def test_invalid_forward_move():
    pawn = Pawn("w")
    pawn.set_board(DummyBoard())

    assert not pawn.is_valid_move(
        5,
        3,
        5,
        4,
        None,
    )


def test_two_step_path():
    pawn = Pawn("w")

    assert pawn.get_path_cells(
        6,
        2,
        4,
        2,
    ) == [
        (5, 2)
    ]


def test_one_step_path():
    pawn = Pawn("w")

    assert pawn.get_path_cells(
        6,
        2,
        5,
        2,
    ) == []