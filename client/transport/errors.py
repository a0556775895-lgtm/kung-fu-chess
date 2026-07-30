"""Stable client transport failures shared by the facade and lobby."""


class AuthenticationRejectedError(ConnectionError):
    """The server refused registration or login during the handshake."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MatchmakingTimeoutError(TimeoutError):
    """No compatible opponent was found before the server queue deadline."""


class ReconnectFailedError(ConnectionError):
    """The active game session could not be restored inside its grace period."""
