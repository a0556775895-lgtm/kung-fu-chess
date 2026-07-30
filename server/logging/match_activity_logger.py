"""Structured rotating activity log owned by one Match."""

import logging


class MatchActivityLogger:
    """Write safe key/value activity entries for one game."""

    def __init__(self, game_id: str, logger: logging.Logger):
        if not isinstance(game_id, str) or not game_id:
            raise ValueError("INVALID_GAME_ID")
        if not isinstance(logger, logging.Logger):
            raise TypeError("LOGGER_REQUIRED")
        self._game_id = game_id
        self._logger = logger
        self._closed = False

    def record(
        self,
        event_type: str,
        *,
        server_time_ms: int,
        request_id: str | None = None,
        user_id: int | None = None,
        **details,
    ) -> None:
        """Write one structured line unless this match log is already closed."""
        if self._closed:
            return
        fields = [
            f"game_id={self._game_id}",
            f"event={event_type}",
            f"server_time_ms={server_time_ms}",
        ]
        if request_id is not None:
            fields.append(f"request_id={request_id}")
        if user_id is not None:
            fields.append(f"user_id={user_id}")
        fields.extend(
            f"{key}={value}"
            for key, value in sorted(details.items())
            if value is not None
        )
        self._logger.info(" ".join(fields))

    def close(self) -> None:
        """Flush and close every handler owned by the match logger once."""
        if self._closed:
            return
        self._closed = True
        for handler in tuple(self._logger.handlers):
            self._logger.removeHandler(handler)
            handler.close()

    @property
    def is_closed(self) -> bool:
        return self._closed
