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
from networking.protocols.game import (
    JoinRequest,
    ProtocolError,
    encode_error,
    parse_join,
)
from networking.protocols.room import (
    CancelRoomRequest,
    CreateRoomRequest,
    RoomProtocolError,
    encode_room_cancelled,
    encode_room_created,
    encode_room_joined,
    parse_room_request,
)
from server import config
from server.game.admission import AdmissionPlayer, GameAdmission
from server.game.controller import GameController
from server.game.game_registry import GameRegistry
from server.game.room_registry import RoomRegistry
from server.game.tick_loop import run_tick_loop
from server.services.matchmaker import (
    Matchmaker,
    MatchmakingTimeoutError,
)
from server.services.reconnect import ReconnectError, ReconnectService
from server.services.room_service import (
    RoomCancelledError,
    RoomService,
    RoomServiceError,
)
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
        room_registry=None,
        room_code_factory=None,
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
        self._room_registry = (
            room_registry if room_registry is not None else RoomRegistry()
        )
        self._rooms = RoomService(
            self._room_registry,
            self._admission.admit_pair,
            room_code_factory=room_code_factory,
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
        await self._rooms.close()
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

            context = await self._admit_authenticated(connection, session)
            if context is None:
                return
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

    async def _admit_authenticated(
        self,
        connection: ServerConnection,
        session,
    ):
        """Route authenticated lobby commands until one creates a live context."""
        while True:
            message = await connection.recv()
            operation = (
                message.strip().split(maxsplit=1)[0]
                if isinstance(message, str) and message.strip()
                else ""
            )
            if operation not in {
                "CREATE_ROOM",
                "JOIN_ROOM",
                "CANCEL_ROOM",
            }:
                return await self._handle_matchmaking_join(
                    connection,
                    session,
                    message,
                )

            try:
                request = parse_room_request(message)
            except RoomProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                continue

            if request.session_token != session.token:
                await connection.send(
                    encode_error(request.request_id, "invalid_session_token")
                )
                continue

            if isinstance(request, CancelRoomRequest):
                await self._cancel_room(connection, request)
                continue

            player = self._room_player(session, request, connection)
            rejection = self._admission.rejection_for(player.request)
            if rejection is not None:
                await connection.send(rejection)
                continue

            if isinstance(request, CreateRoomRequest):
                result = await self._create_and_wait_for_room(
                    connection,
                    player,
                )
                if result is not None:
                    return result.context
                continue

            try:
                result = await self._rooms.join(request.room_code, player)
            except RoomServiceError as exc:
                await connection.send(
                    encode_error(request.request_id, exc.reason)
                )
                continue
            await connection.send(
                encode_room_joined(request.request_id, request.room_code)
            )
            return result.context

    async def _handle_matchmaking_join(
        self,
        connection: ServerConnection,
        session,
        message: str,
    ):
        """Preserve the existing JOIN-based matchmaking path."""
        try:
            join_request = parse_join(message)
        except ProtocolError as exc:
            await connection.send(encode_error("0", str(exc).lower()))
            await connection.close(code=1008, reason="invalid_join")
            return None

        if join_request.session_token != session.token:
            await connection.send(
                encode_error(join_request.request_id, "invalid_session_token")
            )
            await connection.close(code=1008, reason="join_rejected")
            return None

        rejection = self._admission.rejection_for(join_request)
        if rejection is not None:
            await connection.send(rejection)
            await connection.close(code=1008, reason="join_rejected")
            return None

        player = AdmissionPlayer(session, join_request, connection)
        try:
            result, unexpected_message = await self._wait_for_admission(
                connection,
                self._matchmaker.find_or_wait(player),
                f"matchmaking-{session.user_id}",
            )
        except MatchmakingTimeoutError:
            await connection.send(
                encode_error(join_request.request_id, "match_timeout")
            )
            await connection.close(code=1008, reason="match_timeout")
            return None
        if unexpected_message is not None:
            await connection.send(
                encode_error(join_request.request_id, "unexpected_lobby_message")
            )
            return None
        return result.context

    async def _create_and_wait_for_room(
        self,
        connection: ServerConnection,
        creator: AdmissionPlayer,
    ):
        """Create one room and wait for either a joiner or its cancellation."""
        try:
            waiting = await self._rooms.create(creator)
        except RoomServiceError as exc:
            await connection.send(
                encode_error(creator.request.request_id, exc.reason)
            )
            return None

        room_code = waiting.room.room_code
        await connection.send(
            encode_room_created(creator.request.request_id, room_code)
        )

        while True:
            try:
                result, message = await self._wait_for_admission(
                    connection,
                    asyncio.shield(waiting.admission),
                    f"room-{room_code}-{creator.session.user_id}",
                )
            except RoomCancelledError:
                return None
            except ConnectionClosed:
                await self._cancel_waiting_room(
                    room_code,
                    creator.session.token,
                )
                await asyncio.gather(
                    waiting.admission,
                    return_exceptions=True,
                )
                raise

            if result is not None:
                return result

            try:
                request = parse_room_request(message)
            except RoomProtocolError as exc:
                await connection.send(encode_error("0", str(exc).lower()))
                continue

            if not isinstance(request, CancelRoomRequest):
                await connection.send(
                    encode_error(request.request_id, "room_waiting")
                )
                continue
            if request.session_token != creator.session.token:
                await connection.send(
                    encode_error(request.request_id, "invalid_session_token")
                )
                continue
            if request.room_code != room_code:
                await connection.send(
                    encode_error(request.request_id, "room_not_found")
                )
                continue

            await self._cancel_room(connection, request)
            await asyncio.gather(
                waiting.admission,
                return_exceptions=True,
            )
            return None

    async def _cancel_room(
        self,
        connection: ServerConnection,
        request: CancelRoomRequest,
    ) -> bool:
        """Apply one cancellation request and send its correlated response."""
        try:
            await self._rooms.cancel(
                request.room_code,
                request.session_token,
            )
        except RoomServiceError as exc:
            await connection.send(
                encode_error(request.request_id, exc.reason)
            )
            return False
        await connection.send(
            encode_room_cancelled(request.request_id, request.room_code)
        )
        return True

    async def _cancel_waiting_room(
        self,
        room_code: str,
        creator_token: str,
    ) -> None:
        """Remove an abandoned waiting room without sending to a closed socket."""
        try:
            await self._rooms.cancel(room_code, creator_token)
        except RoomServiceError:  # pragma: no cover - concurrent cleanup guard
            return

    @staticmethod
    def _room_player(session, request, connection) -> AdmissionPlayer:
        """Adapt a room request to the existing game-admission contract."""
        join_request = JoinRequest(
            request.request_id,
            request.session_token,
            request.requested_config,
        )
        return AdmissionPlayer(session, join_request, connection)

    @staticmethod
    async def _wait_for_admission(
        connection: ServerConnection,
        admission,
        task_name: str,
    ) -> tuple[object | None, object | None]:
        """Wait for admission or one message using the same race for both paths."""
        async def await_admission():
            return await admission

        admission_task = asyncio.create_task(
            await_admission(),
            name=task_name,
        )
        message_task = asyncio.create_task(
            connection.recv(),
            name=f"{task_name}-message",
        )
        done, _ = await asyncio.wait(
            {admission_task, message_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if admission_task in done:
            message_task.cancel()
            await asyncio.gather(message_task, return_exceptions=True)
            return admission_task.result(), None

        admission_task.cancel()
        await asyncio.gather(admission_task, return_exceptions=True)
        return None, message_task.result()
