"""Atomically persist one completed game and both resulting Elo ratings."""

from server.dal.repository import DuplicateGameCompletionError
from server.game.game_result import GameResult
from server.services.elo import calculate_elo


class GameCompletionService:
    """Coordinate repositories and Elo calculation inside one UnitOfWork."""

    def __init__(self, unit_of_work_factory):
        if not callable(unit_of_work_factory):
            raise TypeError("UNIT_OF_WORK_FACTORY_NOT_CALLABLE")
        self._unit_of_work_factory = unit_of_work_factory

    def complete(
        self,
        *,
        match_instance_id: str,
        white_user_id: int,
        black_user_id: int,
        result: GameResult,
    ):
        """Save one idempotent completion, rolling back every partial change."""
        self._validate_inputs(
            match_instance_id,
            white_user_id,
            black_user_id,
            result,
        )

        try:
            with self._unit_of_work_factory() as unit_of_work:
                existing = unit_of_work.games.get_by_match_instance_id(
                    match_instance_id
                )
                if existing is not None:
                    return existing

                white = unit_of_work.users.get_by_id(white_user_id)
                black = unit_of_work.users.get_by_id(black_user_id)
                if white is None or black is None:
                    raise KeyError("GAME_PLAYER_NOT_FOUND")

                ratings = calculate_elo(
                    white.rating,
                    black.rating,
                    result.winner_color,
                )
                unit_of_work.users.update_rating(
                    white.id,
                    ratings.white_rating,
                )
                unit_of_work.users.update_rating(
                    black.id,
                    ratings.black_rating,
                )
                return unit_of_work.games.record_game(
                    match_instance_id=match_instance_id,
                    white_user_id=white.id,
                    black_user_id=black.id,
                    winner_color=str(result.winner_color),
                    finish_reason=result.reason.value,
                    white_rating_before=white.rating,
                    black_rating_before=black.rating,
                    white_rating_after=ratings.white_rating,
                    black_rating_after=ratings.black_rating,
                    duration_ms=result.duration_ms,
                )
        except DuplicateGameCompletionError:
            with self._unit_of_work_factory() as unit_of_work:
                existing = unit_of_work.games.get_by_match_instance_id(
                    match_instance_id
                )
                if existing is None:  # pragma: no cover - unique conflict guarantees the row
                    raise
                return existing

    @staticmethod
    def _validate_inputs(
        match_instance_id,
        white_user_id,
        black_user_id,
        result,
    ) -> None:
        if not isinstance(match_instance_id, str) or not match_instance_id:
            raise ValueError("INVALID_MATCH_INSTANCE_ID")
        for user_id in (white_user_id, black_user_id):
            if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("INVALID_PLAYER_ID")
        if white_user_id == black_user_id:
            raise ValueError("PLAYERS_MUST_BE_DIFFERENT")
        if not isinstance(result, GameResult):
            raise ValueError("INVALID_GAME_RESULT")
