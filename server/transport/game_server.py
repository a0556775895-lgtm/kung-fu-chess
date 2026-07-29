"""Async WebSocket listener, player connections, and authoritative server tick."""
"""שער הכניסה לשרת"""
import asyncio

from websockets.exceptions import ConnectionClosed
from websockets.asyncio.server import Server, ServerConnection, serve

from networking.protocols.auth import (
    AuthProtocolError,
    AuthResponse,
    RegisterRequest,
    encode_auth_ok,
    parse_auth_request,
)
from networking.protocols.game import ProtocolError, encode_error, parse_join
from server import config
from server.game.admission import AdmissionPlayer, GameAdmission
from server.game.controller import GameController
from server.game.game_registry import GameRegistry
from server.game.tick_loop import run_tick_loop
from server.services.matchmaker import (
    Matchmaker,
    MatchmakingTimeoutError,
)
from server.services.reconnect import ReconnectError, ReconnectService
from server.services.session_registry import SessionRegistry
from server.services.auth import AuthError
from server.transport.connection_io import run_connection_io


class GameServer:
    """Own the WebSocket listener and provide explicit start/stop operations."""

    def __init__(
        self,
        host: str = config.HOST,
        port: int = config.PORT,
        registry=None,
        session_registry=None,
        auth_service=None,
        completion_service=None,
        match_rating_range: int = config.MATCHMAKING_RATING_RANGE,
        match_timeout_seconds: float = config.MATCHMAKING_TIMEOUT_SECONDS,
        reconnect_grace_period_seconds: float = (
            config.RECONNECT_GRACE_PERIOD_SECONDS
        ),
    ):
        if auth_service is None:
            raise TypeError("AUTH_SERVICE_REQUIRED")
        self._host = host
        self._port = port
        self._reconnect_grace_period_seconds = reconnect_grace_period_seconds
        self._server: Server | None = None
        self._tick_task = None
        self._closing = False
        self._registry = registry if registry is not None else GameRegistry()
        self._sessions = (
            session_registry if session_registry is not None else SessionRegistry()
        )
        self._auth_service = auth_service
        self._admission = GameAdmission(
            self._registry,
            completion_service=completion_service,
        )
        self._matchmaker = Matchmaker(
            self._admission.admit_pair,
            rating_range=match_rating_range,
            timeout_seconds=match_timeout_seconds,
        )
        self._reconnect = ReconnectService(
            self._sessions,
            self._registry,
            self._admission,
            grace_period_seconds=reconnect_grace_period_seconds,
        )
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
        """מפעילה את השרת"""
        if self._server is not None:
            raise RuntimeError("server_already_running")
        self._closing = False
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
        self._closing = True
        tick_task = self._tick_task
        self._tick_task = None
        if tick_task is not None:
            tick_task.cancel()
            await asyncio.gather(tick_task, return_exceptions=True)
        server.close()
        await server.wait_closed()
        await self._reconnect.close()
        self._sessions.clear()

    async def _handle_connection(self, connection: ServerConnection) -> None:
        """Route one token-bearing JOIN to matchmaking or session restoration."""
        context = None
        session = None
        try:
            first_message = await connection.recv()
            if (
                isinstance(first_message, str)
                and first_message.startswith("JOIN ")
            ):
                try:
                    join_request = parse_join(first_message)
                except ProtocolError as exc:
                    await connection.send(encode_error("0", str(exc).lower()))
                    await connection.close(code=1008, reason="invalid_join")
                    return

                try:
                    session, result = await self._reconnect.restore(
                        join_request,
                        connection,
                    )
                except ReconnectError as exc:
                    await connection.send(
                        encode_error(join_request.request_id, exc.reason)
                    )
                    await connection.close(code=1008, reason="reconnect_rejected")
                    return

                context = result.context
                await run_connection_io(context, self._controller)
                return  # pragma: no cover - connection loop exits by ConnectionClosed

            try:
                auth_request = parse_auth_request(first_message)
            except AuthProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                await connection.close(code=1008, reason="invalid_auth_request")
                return

            try:
                operation = (
                    self._auth_service.register
                    if isinstance(auth_request, RegisterRequest)
                    else self._auth_service.login
                )
                user = await asyncio.to_thread(
                    operation,
                    auth_request.username,
                    auth_request.password,
                )
            except AuthError as exc:
                await connection.send(
                    encode_error(auth_request.request_id, exc.reason)
                )
                await connection.close(code=1008, reason="authentication_rejected")
                return

            session = self._sessions.create(
                user.id,
                user.username,
                user.rating,
            )
            if session is None:
                await connection.send(
                    encode_error(auth_request.request_id, "user_already_connected")
                )
                await connection.close(code=1008, reason="user_already_connected")
                return

            await connection.send(
                encode_auth_ok(
                    AuthResponse(
                        request_id=auth_request.request_id,
                        user_id=user.id,
                        username=user.username,
                        rating=user.rating,
                        session_token=session.token,
                        reconnect_grace_seconds=(
                            self._reconnect_grace_period_seconds
                        ),
                    )
                )
            )

            try:
                join_request = parse_join(await connection.recv())
            except ProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                await connection.close(code=1008, reason="invalid_join")
                return

            if join_request.session_token != session.token:
                await connection.send(
                    encode_error(join_request.request_id, "invalid_session_token")
                )
                await connection.close(code=1008, reason="join_rejected")
                return

            rejection = self._admission.rejection_for(join_request)
            if rejection is not None:
                await connection.send(rejection)
                await connection.close(code=1008, reason="join_rejected")
                return

            player = AdmissionPlayer(
                session=session,
                request=join_request,
                websocket=connection,
            )
            try:
                result = await self._wait_for_match(connection, player)
            except MatchmakingTimeoutError:
                await connection.send(
                    encode_error(join_request.request_id, "match_timeout")
                )
                await connection.close(code=1008, reason="match_timeout")
                return
            if result is None:
                return

            context = result.context
            await run_connection_io(context, self._controller)
        except ConnectionClosed:
            pass
        finally:
            if context is not None:
                if self._closing:
                    self._admission.release(context)
                    self._sessions.release(session.token)
                else:
                    await self._reconnect.disconnect(session, context)
            elif session is not None:
                self._sessions.release(session.token)

    async def _wait_for_match(
        self,
        connection: ServerConnection,
        player: AdmissionPlayer,
    ):
        """Wait for pairing while removing a client that disconnects in queue."""
        match_task = asyncio.create_task(
            self._matchmaker.find_or_wait(player),
            name=f"matchmaking-{player.session.user_id}",
        )
        closed_task = asyncio.create_task(
            connection.wait_closed(),
            name=f"queue-connection-{player.session.user_id}",
        )
        done, _ = await asyncio.wait(
            {match_task, closed_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if match_task in done:
            closed_task.cancel()
            await asyncio.gather(closed_task, return_exceptions=True)
            return match_task.result()

        match_task.cancel()
        await asyncio.gather(match_task, return_exceptions=True)
        return None
