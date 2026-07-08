import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from knight import Knight


def test_constructor():
    knight = Knight("b")

    assert knight.color == "b"
    assert knight.symbol == "N"
    assert knight.get_move_time() == 3000


def test_move_two_one():
    knight = Knight("w")

    assert knight.is_valid_move(4, 4, 6, 5, None)


def test_move_one_two():
    knight = Knight("w")

    assert knight.is_valid_move(4, 4, 5, 6, None)


def test_move_negative_direction():
    knight = Knight("w")

    assert knight.is_valid_move(4, 4, 2, 3, None)


def test_move_negative_other_direction():
    knight = Knight("w")

    assert knight.is_valid_move(4, 4, 3, 2, None)


def test_invalid_vertical():
    knight = Knight("w")

    assert not knight.is_valid_move(4, 4, 5, 4, None)


def test_invalid_horizontal():
    knight = Knight("w")

    assert not knight.is_valid_move(4, 4, 4, 6, None)


def test_invalid_diagonal():
    knight = Knight("w")

    assert not knight.is_valid_move(4, 4, 5, 5, None)


def test_invalid_same_square():
    knight = Knight("w")

    assert not knight.is_valid_move(4, 4, 4, 4, None)


def test_invalid_far_move():
    knight = Knight("w")

    assert not knight.is_valid_move(4, 4, 7, 7, None)