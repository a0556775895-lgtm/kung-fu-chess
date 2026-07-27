"""Rating-bucket matchmaking with bounded lookup and asynchronous waiting."""
"""אחראי על מציאת זוג מתאים, מחפש בטבלת גיבוב"""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from itertools import count

from networking.protocols.game import JoinRequest
from server.services.session_registry import ActiveSession


class MatchmakingTimeoutError(TimeoutError):
    """No compatible opponent arrived before the configured deadline."""


class AlreadyQueuedError(ValueError):
    """The same authenticated session tried to enter the queue twice."""


@dataclass(frozen=True, slots=True)
class MatchmakingPlayer:
    """Everything needed to turn one queued session into a live connection."""

    session: ActiveSession
    request: JoinRequest
    websocket: object = None


@dataclass(slots=True)
class _WaitingEntry:
    player: MatchmakingPlayer
    future: asyncio.Future
    sequence: int


class Matchmaker:
    """Pair the closest eligible ratings without scanning every waiting player."""

    def __init__(
        self,
        pair_factory,
        *,
        rating_range: int,
        timeout_seconds: float,
    ):
        if not callable(pair_factory):
            raise TypeError("PAIR_FACTORY_NOT_CALLABLE")
        if (
            isinstance(rating_range, bool)
            or not isinstance(rating_range, int)
            or rating_range < 0
        ):
            raise ValueError("INVALID_RATING_RANGE")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds <= 0
        ):
            raise ValueError("INVALID_MATCH_TIMEOUT")

        self._pair_factory = pair_factory
        self._rating_range = rating_range
        self._timeout_seconds = float(timeout_seconds)
        self._waiting_by_rating = {}
        self._rating_by_token = {}
        self._sequence = count()
        self._lock = asyncio.Lock()

    async def find_or_wait(self, player: MatchmakingPlayer):
        """Return this player's admission after pairing, or raise on timeout."""
        token = player.session.token
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        async with self._lock:
            if token in self._rating_by_token:
                raise AlreadyQueuedError(token)

            opponent = self._find_candidate(player.session.rating)
            if opponent is not None:
                self._remove(opponent.player.session.token)
                try:
                    results = self._pair_factory(opponent.player, player)
                    opponent_result = results[opponent.player.session.token]
                    player_result = results[token]
                except BaseException as exc:
                    opponent.future.set_exception(exc)
                    raise
                opponent.future.set_result(opponent_result)
                return player_result

            entry = _WaitingEntry(player, future, next(self._sequence))
            bucket = self._waiting_by_rating.setdefault(
                player.session.rating,
                OrderedDict(),
            )
            bucket[token] = entry
            self._rating_by_token[token] = player.session.rating

        try:
            return await asyncio.wait_for(
                asyncio.shield(future),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            async with self._lock:
                if future.done():
                    return future.result()
                self._remove(token)
            raise MatchmakingTimeoutError(token) from exc
        except asyncio.CancelledError:
            async with self._lock:
                if token in self._rating_by_token:
                    self._remove(token)
            raise

    def _find_candidate(self, rating: int) -> _WaitingEntry | None:
        """Choose closest rating, then oldest arrival, from bucket heads only."""
        for distance in range(self._rating_range + 1):
            candidates = []
            lower = rating - distance
            upper = rating + distance
            for candidate_rating in (
                (lower,) if lower == upper else (lower, upper)
            ):
                bucket = self._waiting_by_rating.get(candidate_rating)
                if bucket:
                    candidates.append(next(iter(bucket.values())))
            if candidates:
                return min(candidates, key=lambda entry: entry.sequence)
        return None

    def _remove(self, token: str) -> _WaitingEntry:
        rating = self._rating_by_token.pop(token)
        bucket = self._waiting_by_rating[rating]
        entry = bucket.pop(token)
        if not bucket:
            del self._waiting_by_rating[rating]
        return entry

    @property
    def waiting_count(self) -> int:
        """Return the number of sessions currently waiting for an opponent."""
        return len(self._rating_by_token)

    @property
    def bucket_count(self) -> int:
        """Return the number of non-empty exact-rating buckets."""
        return len(self._waiting_by_rating)
