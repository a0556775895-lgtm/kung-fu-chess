"""Stable public facade for the client's WebSocket transport."""

from networking.models.standard_game_config import STANDARD_GAME_CONFIG
from client.transport.connection_state import ConnectionState, ConnectionStatus
from client.transport.errors import (
    AuthenticationRejectedError,
    MatchmakingTimeoutError,
    ReconnectFailedError,
)
from client.transport.websocket_transport import (
    WebSocketTransport,
)


class NetworkClient:
    """Public network API used by the graphical client."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        requested_config=STANDARD_GAME_CONFIG,
        *,
        register: bool = False,
        connect_timeout: float = 5.0,
        match_timeout: float = 65.0,
        reconnect_retry_seconds: float = 0.25,
        queue_size: int = 256,
    ):
        """Configure the hidden transport without opening a connection."""
        self._transport = WebSocketTransport(
            uri,
            username,
            password,
            requested_config,
            register=register,
            connect_timeout=connect_timeout,
            match_timeout=match_timeout,
            reconnect_retry_seconds=reconnect_retry_seconds,
            queue_size=queue_size,
        )

    @property
    def is_connected(self) -> bool:
        """Whether the client currently owns a restored game connection."""
        return self._transport.is_connected

    @property
    def connection_status(self) -> ConnectionStatus:
        """Return the presentation-safe lifecycle status."""
        return self._transport.connection_status

    @property
    def room_code(self) -> str | None:
        """Return the active room code when one exists."""
        return self._transport.room_code

    @property
    def lobby_error(self) -> str | None:
        """Return the latest recoverable lobby rejection."""
        return self._transport.lobby_error

    @property
    def config_response(self):
        """Return the server's authoritative game configuration."""
        return self._transport.config_response

    @property
    def auth_response(self):
        """Return the successful authentication response."""
        return self._transport.auth_response

    @property
    def session_token(self) -> str:
        """Return the authenticated session token."""
        return self._transport.session_token

    @property
    def initial_state(self):
        """Return the first authoritative game snapshot."""
        return self._transport.initial_state

    @property
    def failure(self):
        """Return a terminal background failure, if one occurred."""
        return self._transport.failure

    def start(self, timeout: float | None = None) -> None:
        """Authenticate, enter matchmaking, and wait for a game."""
        self._transport.start(timeout)

    def authenticate(self, timeout: float | None = None) -> None:
        """Authenticate and stop in the lobby."""
        self._transport.authenticate(timeout)

    def start_matchmaking(self) -> None:
        """Enter rating-based matchmaking from the lobby."""
        self._transport.start_matchmaking()

    def create_room(self) -> None:
        """Create a private room from the lobby."""
        self._transport.create_room()

    def join_room(self, room_code: str) -> None:
        """Join a private room by code."""
        self._transport.join_room(room_code)

    def cancel_room(self) -> None:
        """Cancel a private room created by this client."""
        self._transport.cancel_room()

    def wait_for_game(self, timeout: float | None = None) -> None:
        """Wait until a lobby operation admits the client to a game."""
        self._transport.wait_for_game(timeout)

    def send(self, message: str) -> None:
        """Send one game-protocol message."""
        self._transport.send(message)

    def drain_messages(self) -> list[str]:
        """Return and remove all currently queued server messages."""
        return self._transport.drain_messages()

    def close(self, timeout: float = 5.0) -> None:
        """Stop the background transport and release the socket."""
        self._transport.close(timeout)
