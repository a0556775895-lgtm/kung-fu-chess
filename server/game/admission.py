"""Atomic player admission and authoritative Match configuration selection."""

import asyncio
from dataclasses import dataclass
import uuid

from boardio.board_factory import create_board, is_supported_game_config
from engine.game_engine import GameEngine
from model.piece import PieceColor
from networking.protocol import (
    JoinRequest,
    encode_config_accepted,
    encode_config_overridden,
    encode_error,
)
from server import config as server_config
from server.game.match import Match
from server.transport.connection import ConnectionContext, ConnectionRole


@dataclass(frozen=True)
class AdmissionResult:
    """Either an admitted context and Match, or one wire rejection message."""

    context: ConnectionContext | None
    match: Match | None
    rejection: str | None = None

    @property
    def is_accepted(self) -> bool:
        """Whether the connection received a player slot."""
        return self.context is not None


class GameAdmission:
    """Admit at most two players to the default Match without color races."""

    def __init__(
        self,
        registry,
        game_id: str = server_config.DEFAULT_GAME_ID,
        connection_id_factory=None,
    ):
        self._registry = registry
        self._game_id = game_id
        self._connection_id_factory = connection_id_factory or (lambda: uuid.uuid4().hex)
        self._lock = asyncio.Lock()

    async def admit(
        self,
        request: JoinRequest,
        websocket=None,
        user_id: str | None = None,
    ) -> AdmissionResult:
        """Atomically create/find the Match, assign a free color, and queue initial messages."""
        async with self._lock:
            match = self._get_or_create_match(request)
            if match is None:
                return AdmissionResult(
                    context=None,
                    match=None,
                    rejection=encode_error(request.request_id, "unsupported_game_config"),
                )

            color = self._first_available_color(match)
            if color is None:
                return AdmissionResult(
                    context=None,
                    match=match,
                    rejection=encode_error(request.request_id, "server_full"),
                )

            context = ConnectionContext(
                connection_id=self._connection_id_factory(),
                game_id=match.game_id,
                role=ConnectionRole.PLAYER,
                color=color,
                user_id=user_id,
                websocket=websocket,
            )
            match.add_connection(context)

            if request.requested_config == match.game_config:
                context.enqueue(encode_config_accepted(request.request_id, match.game_config))
            else:
                context.enqueue(encode_config_overridden(request.request_id, match.game_config))
            match.broadcast_state()
            return AdmissionResult(context=context, match=match)

    def release(self, context: ConnectionContext) -> None:
        """Remove a disconnected context if its Match still exists."""
        try:
            match = self._registry.get(context.game_id)
        except KeyError:
            return
        if match.has_connection(context):
            match.remove_connection(context.connection_id)

    def _get_or_create_match(self, request: JoinRequest) -> Match | None:
        try:
            return self._registry.get(self._game_id)
        except KeyError:
            if not is_supported_game_config(request.requested_config):
                return None
            match = Match(
                self._game_id,
                GameEngine(create_board(request.requested_config)),
                game_config=request.requested_config,
            )
            self._registry.add(match)
            return match

    @staticmethod
    def _first_available_color(match: Match) -> PieceColor | None:
        occupied = {
            context.color
            for context in match.connections()
            if context.role is ConnectionRole.PLAYER
        }
        for color in (PieceColor.WHITE, PieceColor.BLACK):
            if color not in occupied:
                return color
        return None
