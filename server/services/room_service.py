"""Coordinate waiting rooms while delegating game creation to GameAdmission."""

import asyncio
from dataclasses import dataclass
import logging
import secrets
import string

from server.game.admission import AdmissionPlayer, AdmissionResult
from server.game.room import Room, RoomStatus
from server.game.room_registry import RoomRegistry
from server.services.session_registry import SessionState


_ROOM_CODE_ALPHABET = string.ascii_uppercase + string.digits
_ROOM_CODE_LENGTH = 6
_MAX_CODE_ATTEMPTS = 10
logger = logging.getLogger(__name__)


class RoomServiceError(ValueError):
    """A room operation rejected with a wire-safe reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class RoomCancelledError(RoomServiceError):
    """Wake a room creator after the waiting room is cancelled."""


@dataclass(frozen=True, slots=True)
class RoomWait:
    """The created room and the future completed when a second player joins."""

    room: Room
    admission: asyncio.Future


@dataclass(slots=True)
class _WaitingRoom:
    room: Room
    creator: AdmissionPlayer
    future: asyncio.Future


class RoomService:
    """Create, pair, and cancel rooms without duplicating Match creation."""

    def __init__(
        self,
        registry: RoomRegistry,
        pair_factory,
        room_code_factory=None,
        spectator_factory=None,
    ):
        if not isinstance(registry, RoomRegistry):
            raise TypeError("ROOM_REGISTRY_REQUIRED")
        if not callable(pair_factory):
            raise TypeError("PAIR_FACTORY_NOT_CALLABLE")
        if room_code_factory is not None and not callable(room_code_factory):
            raise TypeError("ROOM_CODE_FACTORY_NOT_CALLABLE")
        if spectator_factory is not None and not callable(spectator_factory):
            raise TypeError("SPECTATOR_FACTORY_NOT_CALLABLE")
        self._registry = registry
        self._pair_factory = pair_factory
        self._spectator_factory = spectator_factory
        self._room_code_factory = room_code_factory or self._random_room_code
        self._waiting_by_code = {}
        self._lock = asyncio.Lock()

    async def create(self, creator: AdmissionPlayer) -> RoomWait:
        """Create one waiting room for an otherwise idle session."""
        self._validate_player(creator)
        async with self._lock:
            if creator.session.state is not SessionState.LOBBY:
                raise RoomServiceError("session_not_available")

            room = self._create_unique_room(creator)
            future = asyncio.get_running_loop().create_future()
            self._registry.add(room)
            self._waiting_by_code[room.room_code] = _WaitingRoom(
                room,
                creator,
                future,
            )
            creator.session.state = SessionState.WAITING_IN_ROOM
            logger.info(
                "room created room_code=%s creator_user_id=%s",
                room.room_code,
                creator.session.user_id,
            )
            return RoomWait(room, future)

    async def join(
        self,
        room_code: str,
        player: AdmissionPlayer,
    ) -> AdmissionResult:
        """Fill a waiting player seat or attach a spectator to an active room."""
        self._validate_player(player)
        async with self._lock:
            try:
                room = self._registry.get(room_code)
            except KeyError as exc:
                raise RoomServiceError("room_not_found") from exc
            waiting = self._waiting_by_code.get(room_code)
            if waiting is None:
                if room.status is RoomStatus.FINISHED:
                    raise RoomServiceError("room_finished")
                if (
                    room.status is not RoomStatus.ACTIVE
                    or self._spectator_factory is None
                    or room.match is None
                ):
                    raise RoomServiceError("room_not_waiting")
                if player.session.state is not SessionState.LOBBY:
                    raise RoomServiceError("session_not_available")
                try:
                    result = self._spectator_factory(player, room.match)
                except ValueError as exc:
                    raise RoomServiceError(str(exc).lower()) from exc
                logger.info(
                    "spectator joined room_code=%s user_id=%s game_id=%s",
                    room_code,
                    player.session.user_id,
                    room.match.game_id,
                )
                return result

            if waiting.creator.session.token == player.session.token:
                raise RoomServiceError("cannot_join_own_room")
            if player.session.state is not SessionState.LOBBY:
                raise RoomServiceError("session_not_available")

            try:
                results = self._pair_factory(waiting.creator, player)
                creator_result = results[waiting.creator.session.token]
                player_result = results[player.session.token]
                match = creator_result.match
                if match is None or player_result.match is not match:
                    raise RuntimeError("INVALID_ADMISSION_RESULTS")
                waiting.room.attach_match(match)
            except BaseException:
                waiting.creator.session.state = SessionState.WAITING_IN_ROOM
                player.session.state = SessionState.LOBBY
                raise

            del self._waiting_by_code[room_code]
            waiting.future.set_result(creator_result)
            logger.info(
                "room match started room_code=%s game_id=%s "
                "white_user_id=%s black_user_id=%s",
                room_code,
                match.game_id,
                waiting.creator.session.user_id,
                player.session.user_id,
            )
            return player_result

    async def cancel(self, room_code: str, requester_token: str) -> Room:
        """Cancel a waiting room when requested by its creator."""
        async with self._lock:
            waiting = self._get_waiting(room_code)
            if waiting.creator.session.token != requester_token:
                raise RoomServiceError("room_forbidden")

            waiting.room.cancel()
            del self._waiting_by_code[room_code]
            self._registry.remove(room_code)
            waiting.creator.session.state = SessionState.LOBBY
            waiting.future.set_exception(RoomCancelledError("room_cancelled"))
            logger.info(
                "room cancelled room_code=%s creator_user_id=%s",
                room_code,
                waiting.creator.session.user_id,
            )
            return waiting.room

    async def close(self) -> None:
        """Cancel every waiting room during explicit server shutdown."""
        async with self._lock:
            waiting_rooms = tuple(self._waiting_by_code.values())
            self._waiting_by_code.clear()
            for waiting in waiting_rooms:
                waiting.room.cancel()
                self._registry.remove(waiting.room.room_code)
                waiting.creator.session.state = SessionState.LOBBY
                waiting.future.set_exception(
                    RoomCancelledError("server_closed")
                )

    @property
    def waiting_count(self) -> int:
        """Return the number of rooms still waiting for a second player."""
        return len(self._waiting_by_code)

    def _get_waiting(self, room_code: str) -> _WaitingRoom:
        try:
            return self._waiting_by_code[room_code]
        except KeyError as exc:
            reason = (
                "room_not_waiting"
                if room_code in self._registry
                else "room_not_found"
            )
            raise RoomServiceError(reason) from exc

    def _create_unique_room(self, creator: AdmissionPlayer) -> Room:
        for _attempt in range(_MAX_CODE_ATTEMPTS):
            try:
                room = Room(
                    self._room_code_factory(),
                    creator.session.token,
                    creator.request.requested_config,
                )
            except ValueError as exc:
                raise RoomServiceError("invalid_room_code") from exc
            if room.room_code not in self._registry:
                return room
        raise RoomServiceError("room_code_collision")

    @staticmethod
    def _validate_player(player: AdmissionPlayer) -> None:
        if not isinstance(player, AdmissionPlayer):
            raise TypeError("ADMISSION_PLAYER_REQUIRED")

    @staticmethod
    def _random_room_code() -> str:
        return "".join(
            secrets.choice(_ROOM_CODE_ALPHABET)
            for _ in range(_ROOM_CODE_LENGTH)
        )
