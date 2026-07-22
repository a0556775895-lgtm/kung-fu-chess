"""Threaded WebSocket transport for the synchronous graphical client."""

import asyncio
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import uuid

from websockets.asyncio.client import connect

from boardio.board_factory import STANDARD_GAME_CONFIG
from networking.protocol import (
    JoinRequest,
    decode_state,
    encode_join,
    parse_config_response,
)


_STOP = object()


class NetworkClient:
    """Own one WebSocket connection on a background asyncio thread."""

    def __init__(
        self,
        uri: str,
        requested_config=STANDARD_GAME_CONFIG,
        *,
        connect_timeout: float = 5.0,
        queue_size: int = 256,
    ):
        """Store connection settings without opening the socket yet."""
        if not isinstance(uri, str) or not uri:
            raise ValueError("INVALID_SERVER_URI")
        if connect_timeout <= 0:
            raise ValueError("INVALID_CONNECT_TIMEOUT")
        if queue_size <= 0:
            raise ValueError("INVALID_QUEUE_SIZE")

        self._uri = uri
        self._requested_config = requested_config
        self._connect_timeout = connect_timeout
        self._outgoing = Queue(maxsize=queue_size)
        self._incoming = Queue(maxsize=queue_size)
        self._ready = Event()
        self._state_lock = Lock()
        self._thread = None
        self._connected = False
        self._failure = None
        self._config_response = None
        self._initial_state = None

    @property
    def is_connected(self) -> bool:
        """Return whether the handshake completed and the socket is still open."""
        with self._state_lock:
            return self._connected

    @property
    def config_response(self):
        """Return the server's authoritative configuration decision after start()."""
        if self._config_response is None:
            raise RuntimeError("client_not_started")
        return self._config_response

    @property
    def initial_state(self):
        """Return the first validated authoritative snapshot after start()."""
        if self._initial_state is None:
            raise RuntimeError("client_not_started")
        return self._initial_state

    @property
    def failure(self):
        """Expose a background transport failure for the future GUI error screen."""
        with self._state_lock:
            return self._failure

    def start(self, timeout: float | None = None) -> None:
        """Start the network thread and block only until JOIN finishes or fails."""
        wait_timeout = self._connect_timeout + 1.0 if timeout is None else timeout
        if wait_timeout <= 0:
            raise ValueError("INVALID_START_TIMEOUT")

        with self._state_lock:
            if self._thread is not None:
                raise RuntimeError("client_already_started")
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
            raise ConnectionError("client_connection_failed") from self.failure

    def send(self, message: str) -> None:
        """Queue one protocol message without touching the asyncio event loop."""
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
        """Request socket shutdown and wait for the network thread to finish."""
        if timeout <= 0:
            raise ValueError("INVALID_CLOSE_TIMEOUT")
        with self._state_lock:
            thread = self._thread
        if thread is None:
            return

        self._queue_stop_signal()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError("client_close_timeout")

    def _thread_main(self) -> None:
        """Create and destroy the asyncio loop entirely inside its owner thread."""
        try:
            asyncio.run(self._run_connection())
        except BaseException as exc:  # Preserve the original cause for the GUI/main thread.
            with self._state_lock:
                self._failure = exc
        finally:
            with self._state_lock:
                self._connected = False
            self._ready.set()

    async def _run_connection(self) -> None:
        """Perform JOIN, then coordinate the socket reader and single writer."""
        async with connect(self._uri, open_timeout=self._connect_timeout) as websocket:
            join = JoinRequest(f"join-{uuid.uuid4().hex}", self._requested_config)
            await websocket.send(encode_join(join))

            config_message = await asyncio.wait_for(
                websocket.recv(), timeout=self._connect_timeout
            )
            state_message = await asyncio.wait_for(
                websocket.recv(), timeout=self._connect_timeout
            )
            self._config_response = parse_config_response(config_message)
            self._initial_state = decode_state(state_message)

            with self._state_lock:
                self._connected = True
            self._ready.set()

            reader = asyncio.create_task(self._reader_loop(websocket), name="client-reader")
            writer = asyncio.create_task(self._writer_loop(websocket), name="client-writer")
            tasks = {reader, writer}
            done = set()
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                self._queue_stop_signal()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

            for task in done:
                exception = task.exception()
                if exception is not None:
                    raise exception

    async def _reader_loop(self, websocket) -> None:
        """Copy server messages into the thread-safe GUI-facing queue."""
        async for message in websocket:
            if not isinstance(message, str):
                raise TypeError("INCOMING_MESSAGE_NOT_TEXT")
            try:
                self._incoming.put_nowait(message)
            except Full as exc:
                raise RuntimeError("client_incoming_queue_full") from exc

    async def _writer_loop(self, websocket) -> None:
        """Serialize all outbound socket writes from one coroutine."""
        while True:
            message = await asyncio.to_thread(self._outgoing.get)
            if message is _STOP:
                return
            await websocket.send(message)

    def _queue_stop_signal(self) -> None:
        """Wake the writer; during shutdown pending commands may be discarded."""
        while True:
            try:
                self._outgoing.put_nowait(_STOP)
                return
            except Full:
                try:
                    self._outgoing.get_nowait()
                except Empty:  # pragma: no cover - another thread drained it first
                    pass
