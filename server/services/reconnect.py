"""Atomic restoration of disconnected sessions to persistent match seats."""

import asyncio


class ReconnectError(ValueError):
    """A reconnect JOIN cannot be restored to a live match."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ReconnectService:
    """Coordinate session state, match lookup and connection restoration."""

    def __init__(self, sessions, registry, admission):
        self._sessions = sessions
        self._registry = registry
        self._admission = admission
        self._lock = asyncio.Lock()

    async def disconnect(self, session, context) -> bool:
        """Detach a live socket and retain its session while the match is active."""
        async with self._lock:
            try:
                match = self._registry.get(context.game_id)
            except KeyError:
                self._sessions.release(session.token)
                return False

            self._admission.release(context)
            if match.result is not None:
                self._sessions.release(session.token)
                return False

            self._sessions.mark_disconnected(session.token)
            return True

    async def restore(self, request, websocket):
        """Claim a disconnected session and attach a fresh connection atomically."""
        async with self._lock:
            session = self._sessions.get(request.session_token)
            if session is None:
                raise ReconnectError("invalid_session_token")
            if session.is_connected:
                raise ReconnectError("session_already_connected")
            if session.game_id is None or session.color is None:
                raise ReconnectError("reconnect_not_available")

            try:
                match = self._registry.get(session.game_id)
            except KeyError as exc:
                self._sessions.release(session.token)
                raise ReconnectError("game_not_found") from exc
            if match.result is not None:
                self._sessions.release(session.token)
                raise ReconnectError("game_already_finished")

            try:
                result = self._admission.restore(
                    session,
                    request,
                    websocket,
                )
            except BaseException:
                session.is_connected = False
                raise
            self._sessions.mark_connected(session.token)
            return session, result
