class GameState:
    """Tracks game-level state that isn't part of the board's storage:
    the current game clock and whether the game has ended.

    Extracted from `Board._current_time` / `Board._game_over` using the
    exact same pattern already used for `PendingMove` — a small object
    that `Board` holds and delegates to, instead of holding the fields
    directly.
    """

    def __init__(self):
        self._current_time = 0
        self._game_over = False

    @property
    def current_time(self):
        return self._current_time

    def advance_time(self, milliseconds):
        """Advance the game clock by `milliseconds`."""
        self._current_time += milliseconds

    @property
    def game_over(self):
        return self._game_over

    def end_game(self):
        """Mark the game as over. One-directional: a game that has ended
        cannot un-end (mirrors the old code, which only ever set
        `_game_over = True` and never reset it)."""
        self._game_over = True