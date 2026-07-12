import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from old.rook import Rook


def test_constructor():
    rook = Rook("w")

    assert rook.color == "w"
    assert rook.symbol == "R"
    assert rook.move_time == 1000


def test_valid_horizontal_move():
    rook = Rook("w")

    assert rook.is_valid_move(3, 2, 3, 7, None)


def test_valid_vertical_move():
    rook = Rook("w")

    assert rook.is_valid_move(2, 5, 6, 5, None)


def test_invalid_diagonal_move():
    rook = Rook("w")

    assert not rook.is_valid_move(2, 2, 4, 4, None)


def test_invalid_same_square():
    rook = Rook("w")

    assert not rook.is_valid_move(3, 3, 3, 3, None)


def test_horizontal_path_right():
    rook = Rook("w")

    assert rook.get_path_cells(3, 2, 3, 6) == [
        (3, 3),
        (3, 4),
        (3, 5),
    ]


def test_horizontal_path_left():
    rook = Rook("w")

    assert rook.get_path_cells(3, 6, 3, 2) == [
        (3, 5),
        (3, 4),
        (3, 3),
    ]


def test_vertical_path_down():
    rook = Rook("w")

    assert rook.get_path_cells(2, 4, 6, 4) == [
        (3, 4),
        (4, 4),
        (5, 4),
    ]


def test_vertical_path_up():
    rook = Rook("w")

    assert rook.get_path_cells(6, 4, 2, 4) == [
        (5, 4),
        (4, 4),
        (3, 4),
    ]


def test_adjacent_move_has_empty_path():
    rook = Rook("w")

    assert rook.get_path_cells(3, 3, 3, 4) == []