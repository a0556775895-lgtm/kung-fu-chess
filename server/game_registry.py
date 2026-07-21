"""Explicit game-id routing for all active server matches."""


class GameRegistry:
    def __init__(self):
        self._matches = {}

    def add(self, match) -> None:
        if match.game_id in self._matches:
            raise ValueError("GAME_ALREADY_EXISTS")
        self._matches[match.game_id] = match

    def get(self, game_id: str):
        try:
            return self._matches[game_id]
        except KeyError as exc:
            raise KeyError("GAME_NOT_FOUND") from exc

    def remove(self, game_id: str):
        try:
            return self._matches.pop(game_id)
        except KeyError as exc:
            raise KeyError("GAME_NOT_FOUND") from exc

    def __contains__(self, game_id: str) -> bool:
        return game_id in self._matches

    def __len__(self) -> int:
        return len(self._matches)

    def values(self) -> tuple:
        return tuple(self._matches.values())
