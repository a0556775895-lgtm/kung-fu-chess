"""Pure Elo rating calculation for one decisive game result."""

from dataclasses import dataclass

from model.piece import PieceColor


DEFAULT_K_FACTOR = 32
RATING_SCALE = 400


@dataclass(frozen=True, slots=True)
class EloResult:
    """The new ratings after applying one winner-dependent Elo change."""

    white_rating: int
    black_rating: int


def calculate_elo(
    white_rating: int,
    black_rating: int,
    winner_color: PieceColor,
    *,
    k_factor: int = DEFAULT_K_FACTOR,
) -> EloResult:
    """Return new ratings without reading or mutating external state."""
    _validate_rating(white_rating, "INVALID_WHITE_RATING")
    _validate_rating(black_rating, "INVALID_BLACK_RATING")
    if not isinstance(winner_color, PieceColor):
        raise ValueError("INVALID_WINNER_COLOR")
    if isinstance(k_factor, bool) or not isinstance(k_factor, int) or k_factor <= 0:
        raise ValueError("INVALID_K_FACTOR")

    expected_white = 1 / (
        1 + 10 ** ((black_rating - white_rating) / RATING_SCALE)
    )
    actual_white = 1 if winner_color is PieceColor.WHITE else 0
    white_delta = round(k_factor * (actual_white - expected_white))

    return EloResult(
        white_rating=white_rating + white_delta,
        black_rating=black_rating - white_delta,
    )


def _validate_rating(rating: int, reason: str) -> None:
    """Require a non-negative integer and reject bool as an integer subtype."""
    if isinstance(rating, bool) or not isinstance(rating, int) or rating < 0:
        raise ValueError(reason)
