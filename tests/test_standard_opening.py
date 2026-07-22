"""Tests for constructing independent standard-opening boards."""

import pytest

from boardio.board_factory import STANDARD_GAME_CONFIG, create_board
from model.position import Position
from model.game_config import GameConfig


def test_create_standard_board_has_expected_shape_and_pieces():
    board = create_board(STANDARD_GAME_CONFIG)

    pieces = [piece for row in board.get_grid() for piece in row if piece is not None]
    assert (board.rows, board.cols) == (8, 8)
    assert len(pieces) == 32


def test_create_standard_board_returns_independent_state():
    first = create_board(STANDARD_GAME_CONFIG)
    second = create_board(STANDARD_GAME_CONFIG)

    first.remove_piece(Position(0, 0))

    assert first.get_piece_at(Position(0, 0)) is None
    assert second.get_piece_at(Position(0, 0)) is not None


def test_board_factory_rejects_config_without_a_real_preset():
    unsupported = GameConfig(1, 10, 10, "standard")

    with pytest.raises(ValueError, match="UNSUPPORTED_GAME_CONFIG"):
        create_board(unsupported)
