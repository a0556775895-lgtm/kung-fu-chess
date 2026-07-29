"""In-memory lookup for rooms by their stable public code."""

from server.game.room import Room


class RoomRegistry:
    """Own the room-code to Room mapping used by future room services."""

    def __init__(self):
        """Start with no registered rooms."""
        self._rooms = {}

    def add(self, room: Room) -> None:
        """Register one Room and reject invalid values or duplicate codes."""
        if not isinstance(room, Room):
            raise ValueError("INVALID_ROOM")
        if room.room_code in self._rooms:
            raise ValueError("ROOM_ALREADY_EXISTS")
        self._rooms[room.room_code] = room

    def get(self, room_code: str) -> Room:
        """Return the addressed Room or raise ROOM_NOT_FOUND."""
        try:
            return self._rooms[room_code]
        except KeyError as exc:
            raise KeyError("ROOM_NOT_FOUND") from exc

    def remove(self, room_code: str) -> Room:
        """Remove and return a Room when its lifecycle is complete."""
        try:
            return self._rooms.pop(room_code)
        except KeyError as exc:
            raise KeyError("ROOM_NOT_FOUND") from exc

    def __contains__(self, room_code: str) -> bool:
        return room_code in self._rooms

    def __len__(self) -> int:
        return len(self._rooms)

    def values(self) -> tuple[Room, ...]:
        """Return an immutable snapshot of registered rooms."""
        return tuple(self._rooms.values())
