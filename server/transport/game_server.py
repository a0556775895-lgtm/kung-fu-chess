"""Async WebSocket listener with B3.2b player admission handshake."""

from websockets.exceptions import ConnectionClosed
from websockets.asyncio.server import Server, ServerConnection, serve

from networking.protocol import ProtocolError, encode_error, parse_join
from server import config
from server.game.admission import GameAdmission
from server.game.game_registry import GameRegistry


class GameServer:
    """Own the WebSocket listener and provide explicit start/stop operations."""

    def __init__(self, host: str = config.HOST, port: int = config.PORT, registry=None):
        self._host = host
        self._port = port
        self._server: Server | None = None
        self._registry = registry if registry is not None else GameRegistry()
        self._admission = GameAdmission(self._registry)

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
        """Process the initial JOIN handshake; command I/O is added in B3.2c."""
        context = None
        try:
            try:
                request = parse_join(await connection.recv())
            except ProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                await connection.close(code=1008, reason="invalid_join")
                return

            result = await self._admission.admit(request, websocket=connection)
            if not result.is_accepted:
                await connection.send(result.rejection)
                await connection.close(code=1008, reason="join_rejected")
                return

            context = result.context
            while not context.outbound.empty():
                await connection.send(context.outbound.get_nowait())
            await connection.wait_closed()
        except ConnectionClosed:
            pass
        finally:
            if context is not None:
                self._admission.release(context)
