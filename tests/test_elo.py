"""Unit tests for the pure Elo rating calculation."""

from dataclasses import FrozenInstanceError

import pytest

from model.piece import PieceColor
from server.services.elo import EloResult, calculate_elo


def test_equal_ratings_transfer_sixteen_points_to_white_winner():
    result = calculate_elo(1200, 1200, PieceColor.WHITE)

    assert result == EloResult(white_rating=1216, black_rating=1184)


def test_equal_ratings_transfer_sixteen_points_to_black_winner():
    result = calculate_elo(1200, 1200, PieceColor.BLACK)

    assert result == EloResult(white_rating=1184, black_rating=1216)


def test_expected_win_changes_fewer_points_than_upset():
    expected_win = calculate_elo(1400, 1200, PieceColor.WHITE)
    upset = calculate_elo(1200, 1400, PieceColor.WHITE)

    assert expected_win == EloResult(white_rating=1408, black_rating=1192)
    assert upset == EloResult(white_rating=1224, black_rating=1376)


@pytest.mark.parametrize(
    "white_rating,black_rating,winner",
    [
        (1200, 1200, PieceColor.WHITE),
        (1200, 1200, PieceColor.BLACK),
        (1800, 900, PieceColor.WHITE),
        (900, 1800, PieceColor.BLACK),
    ],
)
def test_rating_total_is_conserved(white_rating, black_rating, winner):
    result = calculate_elo(white_rating, black_rating, winner)

    assert result.white_rating + result.black_rating == white_rating + black_rating


def test_custom_k_factor_controls_change_size():
    result = calculate_elo(
        1200,
        1200,
        PieceColor.WHITE,
        k_factor=16,
    )

    assert result == EloResult(white_rating=1208, black_rating=1192)


def test_result_is_immutable():
    result = calculate_elo(1200, 1200, PieceColor.WHITE)

    with pytest.raises(FrozenInstanceError):
        result.white_rating = 9999


@pytest.mark.parametrize(
    "white_rating,black_rating,winner,k_factor,reason",
    [
        (-1, 1200, PieceColor.WHITE, 32, "INVALID_WHITE_RATING"),
        (True, 1200, PieceColor.WHITE, 32, "INVALID_WHITE_RATING"),
        (1200, -1, PieceColor.WHITE, 32, "INVALID_BLACK_RATING"),
        (1200, 1200, "w", 32, "INVALID_WINNER_COLOR"),
        (1200, 1200, PieceColor.WHITE, 0, "INVALID_K_FACTOR"),
        (1200, 1200, PieceColor.WHITE, True, "INVALID_K_FACTOR"),
    ],
)
def test_invalid_inputs_are_rejected(
    white_rating,
    black_rating,
    winner,
    k_factor,
    reason,
):
    with pytest.raises(ValueError, match=reason):
        calculate_elo(
            white_rating,
            black_rating,
            winner,
            k_factor=k_factor,
        )
