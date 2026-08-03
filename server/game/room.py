"""Room metadata and lifecycle around one optional authoritative match."""

from dataclasses import dataclass, field
from enum import Enum
import re

from networking.models.game_config import GameConfig
from server.game.match import Match


_ROOM_CODE_PATTERN = re.compile(r"[A-Z0-9]{4,12}")


class RoomStatus(str, Enum):
    """The externally meaningful stages of a room."""

    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class Room:
    """A stable room identity that may later own one Match."""

    room_code: str
    creator_token: str = field(repr=False)
    game_config: GameConfig
    match: Match | None = field(default=None, init=False)
    _cancelled: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Reject malformed room metadata at the model boundary."""
        if (
            not isinstance(self.room_code, str)
            or _ROOM_CODE_PATTERN.fullmatch(self.room_code) is None
        ):
            raise ValueError("INVALID_ROOM_CODE")
        if (
            not isinstance(self.creator_token, str)
            or not self.creator_token
            or len(self.creator_token) > 256
        ):
            raise ValueError("INVALID_CREATOR_TOKEN")
        if not isinstance(self.game_config, GameConfig):
            raise ValueError("INVALID_GAME_CONFIG")

    @property
    def status(self) -> RoomStatus:
        """Derive status from cancellation and Match state, avoiding duplicate state."""
        if self._cancelled:
            return RoomStatus.CANCELLED
        if self.match is None:
            return RoomStatus.WAITING
        if self.match.result is None:
            return RoomStatus.ACTIVE
        return RoomStatus.FINISHED

    def attach_match(self, match: Match) -> None:
        """Attach the room's single Match when both players are ready."""
        if not isinstance(match, Match):
            raise ValueError("INVALID_MATCH")
        if self._cancelled:
            raise ValueError("ROOM_CANCELLED")
        if self.match is not None:
            raise ValueError("ROOM_ALREADY_ACTIVE")
        self.match = match

    def cancel(self) -> bool:
        """Cancel an unstarted room once; active or finished rooms cannot be cancelled."""
        if self._cancelled:
            return False
        if self.match is not None:
            raise ValueError("ROOM_ALREADY_ACTIVE")
        self._cancelled = True
        return True
