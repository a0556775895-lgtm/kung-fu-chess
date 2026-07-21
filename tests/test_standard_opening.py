"""Tests for constructing independent standard-opening boards."""

from boardio.standard_opening import create_standard_board
from model.position import Position


def test_create_standard_board_has_expected_shape_and_pieces():
    board = create_standard_board()

    pieces = [piece for row in board.get_grid() for piece in row if piece is not None]
    assert (board.rows, board.cols) == (8, 8)
    assert len(pieces) == 32


def test_create_standard_board_returns_independent_state():
    first = create_standard_board()
    second = create_standard_board()

    first.remove_piece(Position(0, 0))

    assert first.get_piece_at(Position(0, 0)) is None
    assert second.get_piece_at(Position(0, 0)) is not None
