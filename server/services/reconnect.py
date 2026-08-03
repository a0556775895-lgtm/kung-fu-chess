"""Atomic restoration of disconnected sessions to persistent match seats."""

import asyncio
import logging

from networking.models.piece import PieceColor
from server import config
from server.game.game_result import FinishReason, GameResult
from server.services.session_registry import SessionState
from server.transport.connection import ConnectionRole

logger = logging.getLogger(__name__)

class ReconnectError(ValueError):
    """A reconnect JOIN cannot be restored to a live match."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ReconnectService:
    """Coordinate session state, match lookup and connection restoration."""

    def __init__(
        self,
        sessions,
        registry,
        admission,
        grace_period_seconds=config.RECONNECT_GRACE_PERIOD_SECONDS,
        sleep=asyncio.sleep,
    ):
        if (
            isinstance(grace_period_seconds, bool)
            or not isinstance(grace_period_seconds, (int, float))
            or grace_period_seconds < 0
        ):
            raise ValueError("INVALID_RECONNECT_GRACE_PERIOD")
        self._sessions = sessions
        self._registry = registry
        self._admission = admission
        self._grace_period_seconds = float(grace_period_seconds)
        self._sleep = sleep
        self._timeouts = {}
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
            is_spectator = context.role is ConnectionRole.SPECTATOR
            if not is_spectator:
                match.pause_for(session.color)
                match.broadcaster.publish_player_disconnected(
                    session.color,
                    self._grace_period_seconds,
                )
            previous_timeout = self._timeouts.pop(session.token, None)
            if previous_timeout is not None:
                previous_timeout.cancel()
            self._timeouts[session.token] = asyncio.create_task(
                self._expire_after_grace(session.token),
                name=f"reconnect-timeout-{session.user_id}",
            )
            logger.info(
                "connection retained user_id=%s game_id=%s role=%s",
                session.user_id,
                context.game_id,
                context.role.value,
            )
            return True

    async def restore(self, request, websocket):
        """Claim a disconnected session and attach a fresh connection atomically."""
        async with self._lock:
            session = self._sessions.get(request.session_token)
            if session is None:
                raise ReconnectError("invalid_session_token")
            if session.is_connected:
                raise ReconnectError("session_already_connected")
            is_spectator = session.state is SessionState.SPECTATING
            if (
                session.game_id is None
                or (not is_spectator and session.color is None)
            ):
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
            timeout = self._timeouts.pop(session.token, None)
            if timeout is not None:
                timeout.cancel()
            if not is_spectator:
                match.resume_for(session.color)
                match.broadcaster.publish_player_reconnected(session.color)
            logger.info(
                "session restored user_id=%s game_id=%s role=%s",
                session.user_id,
                session.game_id,
                result.context.role.value,
            )
            return session, result

    async def close(self) -> None:
        """Cancel every pending grace timer during explicit server shutdown."""
        async with self._lock:
            tasks = tuple(self._timeouts.values())
            self._timeouts.clear()
            for task in tasks:
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _expire_after_grace(self, token: str) -> None:
        """Wait outside the lock, then resolve the disconnect if it is still current."""
        try:
            await self._sleep(self._grace_period_seconds)
            async with self._lock:
                if self._timeouts.get(token) is not asyncio.current_task():
                    return
                self._timeouts.pop(token, None)
                session = self._sessions.get(token)
                if session is None or session.is_connected:
                    return
                try:
                    match = self._registry.get(session.game_id)
                except KeyError:
                    self._sessions.release(token)
                    return
                if session.state is SessionState.SPECTATING:
                    logger.info(
                        "spectator session expired user_id=%s game_id=%s",
                        session.user_id,
                        session.game_id,
                    )
                    self._sessions.release(token)
                    return
                if match.result is None:
                    winner = (
                        PieceColor.BLACK
                        if session.color is PieceColor.WHITE
                        else PieceColor.WHITE
                    )
                    match.finish(GameResult(
                        winner_color=winner,
                        reason=FinishReason.DISCONNECT,
                        duration_ms=match.server_time_ms(),
                    ))
                    logger.info(
                        "player reconnect expired user_id=%s game_id=%s",
                        session.user_id,
                        session.game_id,
                    )
                self._sessions.release(token)
        except asyncio.CancelledError:
            return
