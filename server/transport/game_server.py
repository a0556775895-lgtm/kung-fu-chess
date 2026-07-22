"""Async WebSocket listener, player connections, and authoritative server tick."""

import asyncio

from websockets.exceptions import ConnectionClosed
from websockets.asyncio.server import Server, ServerConnection, serve

from networking.login_protocol import (
    LoginProtocolError,
    encode_login_ok,
    parse_login,
)
from networking.protocol import ProtocolError, encode_error, parse_join
from server import config
from server.game.admission import GameAdmission
from server.game.controller import GameController
from server.game.game_registry import GameRegistry
from server.game.tick_loop import run_tick_loop
from server.services.active_user_registry import ActiveUserRegistry
from server.transport.connection_io import run_connection_io


class GameServer:
    """Own the WebSocket listener and provide explicit start/stop operations."""

    def __init__(
        self,
        host: str = config.HOST,
        port: int = config.PORT,
        registry=None,
        active_users=None,
    ):
        self._host = host
        self._port = port
        self._server: Server | None = None
        self._tick_task = None
        self._registry = registry if registry is not None else GameRegistry()
        self._active_users = (
            active_users if active_users is not None else ActiveUserRegistry()
        )
        self._admission = GameAdmission(self._registry)
        self._controller = GameController(self._registry)

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
        self._tick_task = asyncio.create_task(run_tick_loop(self._registry), name="server-tick")

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
        tick_task = self._tick_task
        self._tick_task = None
        if tick_task is not None:
            tick_task.cancel()
            await asyncio.gather(tick_task, return_exceptions=True)
        server.close()
        await server.wait_closed()

    async def _handle_connection(self, connection: ServerConnection) -> None:
        """Require LOGIN before JOIN, then run authorized game command I/O."""
        context = None
        claimed_username = None
        try:
            try:
                login_request = parse_login(await connection.recv())
            except LoginProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                await connection.close(code=1008, reason="invalid_login")
                return

            if not self._active_users.claim(login_request.username):
                await connection.send(
                    encode_error(login_request.request_id, "username_taken")
                )
                await connection.close(code=1008, reason="username_taken")
                return

            claimed_username = login_request.username
            await connection.send(
                encode_login_ok(login_request.request_id, login_request.username)
            )

            try:
                join_request = parse_join(await connection.recv())
            except ProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                await connection.close(code=1008, reason="invalid_join")
                return

            result = await self._admission.admit(
                join_request,
                websocket=connection,
                user_id=claimed_username,
            )
            if not result.is_accepted:
                await connection.send(result.rejection)
                await connection.close(code=1008, reason="join_rejected")
                return

            context = result.context
            await run_connection_io(context, self._controller)
        except ConnectionClosed:
            pass
        finally:
            if context is not None:
                self._admission.release(context)
            if claimed_username is not None:
                self._active_users.release(claimed_username)
