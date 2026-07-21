"""Async WebSocket server lifecycle; game sessions are added in B3.2."""

from websockets.asyncio.server import Server, ServerConnection, serve

from server import config


class GameServer:
    """Own the WebSocket listener and provide explicit start/stop operations."""

    def __init__(self, host: str = config.HOST, port: int = config.PORT):
        self._host = host
        self._port = port
        self._server: Server | None = None

    @property
    def is_running(self) -> bool:
        """Whether the listener has been started and not yet closed."""
        return self._server is not None

    @property
    def bound_port(self) -> int:
        """Return the actual listening port, including when port 0 was requested."""
        if self._server is None or not self._server.sockets:
            raise RuntimeError("server_not_running")
        return self._server.sockets[0].getsockname()[1]

    async def start(self) -> None:
        """Bind the WebSocket listener without blocking the current task."""
        if self._server is not None:
            raise RuntimeError("server_already_running")
        self._server = await serve(self._handle_connection, self._host, self._port)

    async def serve_forever(self) -> None:
        """Keep an already-started listener alive until it is closed."""
        if self._server is None:
            raise RuntimeError("server_not_running")
        await self._server.serve_forever()

    async def close(self) -> None:
        """Stop accepting connections and wait until the listener is closed."""
        if self._server is None:
            return
        server = self._server
        self._server = None
        server.close()
        await server.wait_closed()

    async def _handle_connection(self, connection: ServerConnection) -> None:
        """Keep a socket alive; game admission and I/O are implemented in B3.2."""
        await connection.wait_closed()
