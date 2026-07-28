"""Threaded WebSocket transport for the synchronous graphical client."""

import asyncio
from dataclasses import dataclass
from enum import Enum
import math
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time
import uuid

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocols.auth import (
    LoginRequest,
    RegisterRequest,
    encode_login,
    encode_register,
    parse_auth_response,
    validate_username,
)
from networking.protocols.game import (
    JoinRequest,
    decode_state,
    encode_join,
    parse_command_response,
    parse_config_response,
)


class AuthenticationRejectedError(ConnectionError):
    """The server refused registration or login during the handshake."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MatchmakingTimeoutError(TimeoutError):
    """No compatible opponent was found before the server queue deadline."""


class ReconnectFailedError(ConnectionError):
    """The active game session could not be restored inside its grace period."""


class _ReconnectRejectedError(ConnectionError):
    """One reconnect JOIN was explicitly rejected by the server."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ConnectionState(str, Enum):
    """Lifecycle states exposed safely to the graphical thread."""

    NOT_STARTED = "NOT_STARTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class ConnectionStatus:
    """Immutable presentation snapshot of the current transport state."""

    state: ConnectionState
    seconds_remaining: int | None = None


class NetworkClient:
    """Own one reconnecting WebSocket transport on a background asyncio thread."""

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
        """Store connection settings without opening the socket yet."""
        if not isinstance(uri, str) or not uri:
            raise ValueError("INVALID_SERVER_URI")
        validate_username(username)
        if not isinstance(password, str):
            raise TypeError("PASSWORD_NOT_TEXT")
        if not isinstance(register, bool):
            raise TypeError("REGISTER_FLAG_NOT_BOOLEAN")
        if connect_timeout <= 0:
            raise ValueError("INVALID_CONNECT_TIMEOUT")
        if match_timeout <= 0:
            raise ValueError("INVALID_MATCH_TIMEOUT")
        if reconnect_retry_seconds <= 0:
            raise ValueError("INVALID_RECONNECT_RETRY")
        if queue_size <= 0:
            raise ValueError("INVALID_QUEUE_SIZE")

        self._uri = uri
        self._username = username
        self._password = password
        self._register = register
        self._requested_config = requested_config
        self._connect_timeout = connect_timeout
        self._match_timeout = match_timeout
        self._reconnect_retry_seconds = reconnect_retry_seconds
        self._outgoing = Queue(maxsize=queue_size)
        self._incoming = Queue(maxsize=queue_size)
        self._ready = Event()
        self._stop_requested = Event()
        self._state_lock = Lock()
        self._thread = None
        self._state = ConnectionState.NOT_STARTED
        self._reconnect_deadline = None
        self._failure = None
        self._auth_response = None
        self._session_token = None
        self._config_response = None
        self._initial_state = None

    @property
    def is_connected(self) -> bool:
        """Whether a fully joined socket currently owns the game session."""
        with self._state_lock:
            return self._state is ConnectionState.CONNECTED

    @property
    def connection_status(self) -> ConnectionStatus:
        """Return current state and a locally calculated reconnect countdown."""
        with self._state_lock:
            state = self._state
            deadline = self._reconnect_deadline
        remaining = (
            max(0, math.ceil(deadline - time.monotonic()))
            if state is ConnectionState.RECONNECTING and deadline is not None
            else None
        )
        return ConnectionStatus(state, remaining)

    @property
    def config_response(self):
        """Return the server's authoritative configuration decision after start()."""
        if self._config_response is None:
            raise RuntimeError("client_not_started")
        return self._config_response

    @property
    def auth_response(self):
        """Return the persistent account confirmation received before JOIN."""
        if self._auth_response is None:
            raise RuntimeError("client_not_started")
        return self._auth_response

    @property
    def session_token(self) -> str:
        """Return the temporary token used for every reconnect JOIN."""
        if self._session_token is None:
            raise RuntimeError("client_not_authenticated")
        return self._session_token

    @property
    def initial_state(self):
        """Return the first validated authoritative snapshot after start()."""
        if self._initial_state is None:
            raise RuntimeError("client_not_started")
        return self._initial_state

    @property
    def failure(self):
        """Expose only a terminal background transport failure."""
        with self._state_lock:
            return self._failure

    def start(self, timeout: float | None = None) -> None:
        """Start the network thread and block only until initial JOIN completes."""
        wait_timeout = (
            self._connect_timeout + self._match_timeout + 1.0
            if timeout is None
            else timeout
        )
        if wait_timeout <= 0:
            raise ValueError("INVALID_START_TIMEOUT")

        with self._state_lock:
            if self._thread is not None:
                raise RuntimeError("client_already_started")
            self._state = ConnectionState.CONNECTING
            self._thread = Thread(
                target=self._thread_main,
                name="network-client",
                daemon=True,
            )
            thread = self._thread

        thread.start()
        if not self._ready.wait(wait_timeout):
            self.close()
            raise TimeoutError("client_start_timeout")
        if self.failure is not None:
            thread.join()
            if isinstance(self.failure, AuthenticationRejectedError):
                raise AuthenticationRejectedError(self.failure.reason) from self.failure
            if isinstance(self.failure, MatchmakingTimeoutError):
                raise MatchmakingTimeoutError("match_timeout") from self.failure
            raise ConnectionError("client_connection_failed") from self.failure

    def send(self, message: str) -> None:
        """Queue one protocol message only while a socket is fully restored."""
        if not isinstance(message, str):
            raise TypeError("OUTGOING_MESSAGE_NOT_TEXT")
        if not self.is_connected:
            raise RuntimeError("client_not_connected")
        try:
            self._outgoing.put_nowait(message)
        except Full as exc:
            raise RuntimeError("client_outgoing_queue_full") from exc

    def drain_messages(self) -> list[str]:
        """Return all server messages currently waiting for the GUI thread."""
        messages = []
        while True:
            try:
                messages.append(self._incoming.get_nowait())
            except Empty:
                return messages

    def close(self, timeout: float = 5.0) -> None:
        """Request intentional shutdown without triggering reconnect."""
        if timeout <= 0:
            raise ValueError("INVALID_CLOSE_TIMEOUT")
        with self._state_lock:
            thread = self._thread
        if thread is None:
            return

        self._stop_requested.set()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError("client_close_timeout")
        with self._state_lock:
            self._state = ConnectionState.CLOSED
            self._reconnect_deadline = None

    def _thread_main(self) -> None:
        """Create and destroy the asyncio loop entirely inside its owner thread."""
        try:
            asyncio.run(self._run_connection())
        except BaseException as exc:
            with self._state_lock:
                self._failure = exc
                self._state = ConnectionState.FAILED
        finally:
            with self._state_lock:
                if self._stop_requested.is_set():
                    self._state = ConnectionState.CLOSED
                self._reconnect_deadline = None
            self._ready.set()

    async def _run_connection(self) -> None:
        """Open the initial session, then supervise every later reconnect."""
        async with connect(self._uri, open_timeout=self._connect_timeout) as websocket:
            await self._perform_initial_handshake(websocket)
            self._set_state(ConnectionState.CONNECTED)
            self._ready.set()
            try:
                await self._run_socket_io(websocket)
            except (ConnectionClosed, OSError):
                pass

        if not self._stop_requested.is_set():
            await self._supervise_reconnects()

    async def _perform_initial_handshake(self, websocket) -> None:
        """Authenticate once, create the session, and wait for matchmaking."""
        request_id_prefix = "register" if self._register else "login"
        request_type = RegisterRequest if self._register else LoginRequest
        encoder = encode_register if self._register else encode_login
        auth_request = request_type(
            f"{request_id_prefix}-{uuid.uuid4().hex}",
            self._username,
            self._password,
        )
        self._password = None
        await websocket.send(encoder(auth_request))
        auth_message = await asyncio.wait_for(
            websocket.recv(),
            timeout=self._connect_timeout,
        )
        if auth_message.startswith("ERR "):
            response = parse_command_response(auth_message)
            if response.request_id != auth_request.request_id:
                raise ConnectionError("auth_request_id_mismatch")
            raise AuthenticationRejectedError(
                response.reason or "authentication_rejected"
            )
        self._auth_response = parse_auth_response(auth_message)
        if self._auth_response.request_id != auth_request.request_id:
            raise ConnectionError("auth_request_id_mismatch")
        self._session_token = self._auth_response.session_token

        config_message, state_message = await self._join(
            websocket,
            timeout=self._match_timeout,
        )
        self._config_response = parse_config_response(config_message)
        self._initial_state = decode_state(state_message)

    async def _supervise_reconnects(self) -> None:
        """Retry token-bearing JOINs until restored, stopped, or grace expires."""
        grace_seconds = self._auth_response.reconnect_grace_seconds
        while not self._stop_requested.is_set():
            deadline = time.monotonic() + grace_seconds
            self._set_state(ConnectionState.RECONNECTING, deadline)
            self._discard_outgoing()

            while not self._stop_requested.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ReconnectFailedError("reconnect_timeout")
                restored = False
                try:
                    async with connect(
                        self._uri,
                        open_timeout=min(self._connect_timeout, remaining),
                    ) as websocket:
                        config_message, state_message = await self._join(
                            websocket,
                            timeout=min(self._connect_timeout, remaining),
                            reconnect=True,
                        )
                        self._config_response = parse_config_response(config_message)
                        decode_state(state_message)
                        self._enqueue_incoming(state_message)
                        self._set_state(ConnectionState.CONNECTED)
                        restored = True
                        await self._run_socket_io(websocket)
                    break
                except _ReconnectRejectedError as exc:
                    if exc.reason != "session_already_connected":
                        raise ReconnectFailedError(exc.reason) from exc
                except (ConnectionClosed, OSError, asyncio.TimeoutError):
                    if restored:
                        break

                await asyncio.sleep(min(
                    self._reconnect_retry_seconds,
                    max(0, deadline - time.monotonic()),
                ))

    async def _join(self, websocket, *, timeout: float, reconnect: bool = False):
        """Send the shared JOIN command and receive config plus a full snapshot."""
        join = JoinRequest(
            f"join-{uuid.uuid4().hex}",
            self._session_token,
            self._requested_config,
        )
        await websocket.send(encode_join(join))
        config_message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        if config_message.startswith("ERR "):
            response = parse_command_response(config_message)
            if response.request_id != join.request_id:
                raise ConnectionError("join_request_id_mismatch")
            if not reconnect and response.reason == "match_timeout":
                raise MatchmakingTimeoutError("match_timeout")
            if reconnect:
                raise _ReconnectRejectedError(
                    response.reason or "reconnect_rejected"
                )
            raise ConnectionError(response.reason or "join_rejected")
        state_message = await asyncio.wait_for(
            websocket.recv(),
            timeout=min(timeout, self._connect_timeout),
        )
        return config_message, state_message

    async def _run_socket_io(self, websocket) -> None:
        """Run one replaceable socket without terminating the network thread."""
        reader = asyncio.create_task(self._reader_loop(websocket), name="client-reader")
        writer = asyncio.create_task(self._writer_loop(websocket), name="client-writer")
        tasks = {reader, writer}
        done = set()
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if not self._stop_requested.is_set():
                self._set_state(ConnectionState.RECONNECTING)

        for task in done:
            exception = task.exception()
            if exception is not None:
                raise exception

    async def _reader_loop(self, websocket) -> None:
        """Copy server messages into the thread-safe GUI-facing queue."""
        async for message in websocket:
            if not isinstance(message, str):
                raise TypeError("INCOMING_MESSAGE_NOT_TEXT")
            self._enqueue_incoming(message)

    async def _writer_loop(self, websocket) -> None:
        """Poll without leaving a blocked worker thread after socket replacement."""
        while not self._stop_requested.is_set():
            try:
                message = self._outgoing.get_nowait()
            except Empty:
                await asyncio.sleep(0.01)
                continue
            await websocket.send(message)

    def _enqueue_incoming(self, message: str) -> None:
        try:
            self._incoming.put_nowait(message)
        except Full as exc:
            raise RuntimeError("client_incoming_queue_full") from exc

    def _discard_outgoing(self) -> None:
        """Never replay a command whose delivery before disconnect is unknown."""
        while True:
            try:
                self._outgoing.get_nowait()
            except Empty:
                return

    def _set_state(
        self,
        state: ConnectionState,
        reconnect_deadline: float | None = None,
    ) -> None:
        with self._state_lock:
            self._state = state
            self._reconnect_deadline = reconnect_deadline
