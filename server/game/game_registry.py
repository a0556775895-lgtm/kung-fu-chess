"""Explicit game-id routing for all active server matches."""


class GameRegistry:
    """Own the active game-id to Match mapping used by server routing."""

    def __init__(self):
        """Start with no registered matches."""
        self._matches = {}

    def add(self, match) -> None:
        """Register a Match and reject duplicate game ids."""
        if match.game_id in self._matches:
            raise ValueError("GAME_ALREADY_EXISTS")
        self._matches[match.game_id] = match

    def get(self, game_id: str):
        """Return the explicitly addressed Match or raise GAME_NOT_FOUND."""
        try:
            return self._matches[game_id]
        except KeyError as exc:
            raise KeyError("GAME_NOT_FOUND") from exc

    def remove(self, game_id: str):
        """Remove and return a Match so its lifecycle can be closed by the caller."""
        try:
            return self._matches.pop(game_id)
        except KeyError as exc:
            raise KeyError("GAME_NOT_FOUND") from exc

    def __contains__(self, game_id: str) -> bool:
        return game_id in self._matches

    def __len__(self) -> int:
        return len(self._matches)

    def values(self) -> tuple:
        """Return an immutable snapshot of currently registered matches."""
        return tuple(self._matches.values())
