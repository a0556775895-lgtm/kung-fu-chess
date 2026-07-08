import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from king import King


def test_constructor():
    king = King("w")

    assert king.color == "w"
    assert king.symbol == "K"
    assert king.get_move_time() == 1000


def test_move_one_step_up():
    king = King("w")

    assert king.is_valid_move(4, 4, 3, 4, None)


def test_move_one_step_down():
    king = King("w")

    assert king.is_valid_move(4, 4, 5, 4, None)


def test_move_one_step_left():
    king = King("w")

    assert king.is_valid_move(4, 4, 4, 3, None)


def test_move_one_step_right():
    king = King("w")

    assert king.is_valid_move(4, 4, 4, 5, None)


def test_move_diagonal():
    king = King("w")

    assert king.is_valid_move(4, 4, 5, 5, None)


def test_move_too_far_vertical():
    king = King("w")

    assert not king.is_valid_move(4, 4, 2, 4, None)


def test_move_too_far_horizontal():
    king = King("w")

    assert not king.is_valid_move(4, 4, 4, 7, None)


def test_move_too_far_diagonal():
    king = King("w")

    assert not king.is_valid_move(4, 4, 6, 6, None)


def test_move_to_same_square():
    king = King("w")

    assert not king.is_valid_move(4, 4, 4, 4, None)