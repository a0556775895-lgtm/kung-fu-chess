import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from queen import Queen


def test_constructor():
    queen = Queen("b")

    assert queen.color == "b"
    assert queen.symbol == "Q"
    assert queen.get_move_time() == 1000


def test_valid_horizontal_move():
    queen = Queen("w")

    assert queen.is_valid_move(3, 2, 3, 7, None)


def test_valid_vertical_move():
    queen = Queen("w")

    assert queen.is_valid_move(2, 5, 6, 5, None)


def test_valid_diagonal_move():
    queen = Queen("w")

    assert queen.is_valid_move(2, 2, 5, 5, None)


def test_valid_reverse_diagonal_move():
    queen = Queen("w")

    assert queen.is_valid_move(5, 5, 2, 2, None)


def test_invalid_knight_move():
    queen = Queen("w")

    assert not queen.is_valid_move(4, 4, 6, 5, None)


def test_invalid_random_move():
    queen = Queen("w")

    assert not queen.is_valid_move(3, 3, 5, 4, None)


def test_invalid_same_square():
    queen = Queen("w")

    assert not queen.is_valid_move(4, 4, 4, 4, None)