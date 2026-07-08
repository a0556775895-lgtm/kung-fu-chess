import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bishop import Bishop


def test_constructor():
    bishop = Bishop("w")

    assert bishop.color == "w"
    assert bishop.symbol == "B"
    assert bishop.get_move_time() == 1000


def test_valid_main_diagonal():
    bishop = Bishop("w")

    assert bishop.is_valid_move(2, 2, 5, 5)


def test_valid_reverse_diagonal():
    bishop = Bishop("w")

    assert bishop.is_valid_move(5, 5, 2, 2)


def test_valid_other_diagonal():
    bishop = Bishop("w")

    assert bishop.is_valid_move(5, 2, 2, 5)


def test_invalid_horizontal():
    bishop = Bishop("w")

    assert not bishop.is_valid_move(2, 2, 2, 5)


def test_invalid_vertical():
    bishop = Bishop("w")

    assert not bishop.is_valid_move(2, 2, 5, 2)


def test_invalid_same_square():
    bishop = Bishop("w")

    assert not bishop.is_valid_move(2, 2, 2, 2)


def test_diagonal_path_down_right():
    bishop = Bishop("w")

    assert bishop.get_path_cells(
        2, 2, 5, 5, None
    ) == [
        (3, 3),
        (4, 4),
    ]


def test_diagonal_path_up_left():
    bishop = Bishop("w")

    assert bishop.get_path_cells(
        5, 5, 2, 2, None
    ) == [
        (4, 4),
        (3, 3),
    ]


def test_diagonal_path_up_right():
    bishop = Bishop("w")

    assert bishop.get_path_cells(
        5, 2, 2, 5, None
    ) == [
        (4, 3),
        (3, 4),
    ]


def test_adjacent_diagonal_has_empty_path():
    bishop = Bishop("w")

    assert bishop.get_path_cells(
        2, 2, 3, 3, None
    ) == []