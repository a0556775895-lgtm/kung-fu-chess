"""Create one isolated Match and two player contexts from an approved pair."""
"""מקבל זוג למשחק ומכין לו את הכל"""
from dataclasses import dataclass
import uuid

from server.boardio.board_factory import create_board, is_supported_game_config
from server.engine.game_engine import GameEngine
from networking.models.piece import PieceColor
from networking.protocols.game import (
    JoinRequest,
    encode_config_accepted,
    encode_config_overridden,
    encode_error,
)
from server.game.match import Match
from server.services.session_registry import ActiveSession, SessionState
from server.transport.connection import ConnectionContext, ConnectionRole


@dataclass(frozen=True, slots=True)
class AdmissionPlayer:
    """Authenticated player data required to create or restore a game seat."""

    session: ActiveSession
    request: JoinRequest
    websocket: object = None


@dataclass(frozen=True)
class AdmissionResult:
    """Either an admitted context and Match, or one wire rejection message."""

    context: ConnectionContext | None
    match: Match | None
    rejection: str | None = None

    @property
    def is_accepted(self) -> bool:
        """Whether matchmaking produced a live player context."""
        return self.context is not None


class GameAdmission:
    """Turn one compatible matchmaking pair into an isolated live Match."""

    def __init__(
        self,
        registry,
        connection_id_factory=None,
        game_id_factory=None,
        completion_service=None,
        match_logger_factory=None,
    ):
        self._registry = registry
        self._connection_id_factory = (
            connection_id_factory or (lambda: uuid.uuid4().hex)
        )
        self._game_id_factory = game_id_factory or (lambda: uuid.uuid4().hex)
        self._completion_service = completion_service
        if match_logger_factory is not None and not callable(match_logger_factory):
            raise TypeError("MATCH_LOGGER_FACTORY_NOT_CALLABLE")
        self._match_logger_factory = match_logger_factory

    @staticmethod
    def rejection_for(request: JoinRequest) -> str | None:
        """Return a wire rejection before unsupported config enters the queue."""
        if not is_supported_game_config(request.requested_config):
            return encode_error(
                request.request_id,
                "unsupported_game_config",
            )
        return None

    def admit_pair(
        self,
        first: AdmissionPlayer,
        second: AdmissionPlayer,
    ) -> dict[str, AdmissionResult]:
        """Create exactly one Match and return each session's personalized result."""
        if first.session.token == second.session.token:
            raise ValueError("PLAYERS_MUST_BE_DIFFERENT")
        if (
            self.rejection_for(first.request) is not None
            or self.rejection_for(second.request) is not None
        ):
            raise ValueError("UNSUPPORTED_GAME_CONFIG")

        game_id = self._game_id_factory()
        if not isinstance(game_id, str) or not game_id:
            raise ValueError("INVALID_GAME_ID")
        match = Match(
            game_id,
            GameEngine(create_board(first.request.requested_config)),
            game_config=first.request.requested_config,
            completion_service=self._completion_service,
            activity_logger=(
                self._match_logger_factory(game_id)
                if self._match_logger_factory is not None
                else None
            ),
        )
        self._registry.add(match)

        first_context = self._create_context(
            first,
            match,
            PieceColor.WHITE,
            ConnectionRole.PLAYER,
        )
        second_context = self._create_context(
            second,
            match,
            PieceColor.BLACK,
            ConnectionRole.PLAYER,
        )
        match.add_connection(first_context)
        match.add_connection(second_context)
        first.session.game_id = game_id
        first.session.color = PieceColor.WHITE
        first.session.state = SessionState.IN_GAME
        second.session.game_id = game_id
        second.session.color = PieceColor.BLACK
        second.session.state = SessionState.IN_GAME

        self._enqueue_config(first_context, first.request, match)
        self._enqueue_config(second_context, second.request, match)
        match.broadcast_state()
        return {
            first.session.token: AdmissionResult(first_context, match),
            second.session.token: AdmissionResult(second_context, match),
        }

    def admit_spectator(
        self,
        spectator: AdmissionPlayer,
        match: Match,
    ) -> AdmissionResult:
        """Attach one authenticated spectator without occupying a player seat."""
        if not isinstance(spectator, AdmissionPlayer):
            raise TypeError("ADMISSION_PLAYER_REQUIRED")
        if not isinstance(match, Match):
            raise TypeError("MATCH_REQUIRED")
        if spectator.session.state is not SessionState.LOBBY:
            raise ValueError("SESSION_NOT_AVAILABLE")
        if match.result is not None:
            raise ValueError("GAME_ALREADY_FINISHED")

        context = self._create_context(
            spectator,
            match,
            None,
            ConnectionRole.SPECTATOR,
        )
        match.add_connection(context)
        spectator.session.game_id = match.game_id
        spectator.session.color = None
        spectator.session.state = SessionState.SPECTATING
        self._enqueue_config(context, spectator.request, match)
        match.send_state(context)
        return AdmissionResult(context, match)

    def release(self, context: ConnectionContext) -> None:
        """Remove a disconnected context if its Match still exists."""
        try:
            match = self._registry.get(context.game_id)
        except KeyError:
            return
        if match.has_connection(context):
            match.remove_connection(context.connection_id)

    def restore(
        self,
        session,
        request: JoinRequest,
        websocket,
    ) -> AdmissionResult:
        """Restore one persistent player seat or spectator subscription."""
        match = self._registry.get(session.game_id)
        player = AdmissionPlayer(
            session=session,
            request=request,
            websocket=websocket,
        )
        role = (
            ConnectionRole.SPECTATOR
            if session.state is SessionState.SPECTATING
            else ConnectionRole.PLAYER
        )
        context = self._create_context(
            player,
            match,
            session.color,
            role,
        )
        match.add_connection(context)
        self._enqueue_config(context, request, match)
        match.send_state(context)
        return AdmissionResult(context, match)

    def _create_context(
        self,
        player: AdmissionPlayer,
        match: Match,
        color: PieceColor | None,
        role: ConnectionRole,
    ) -> ConnectionContext:
        return ConnectionContext(
            connection_id=self._connection_id_factory(),
            game_id=match.game_id,
            role=role,
            color=color,
            user_id=player.session.user_id,
            username=player.session.username,
            session_token=player.session.token,
            websocket=player.websocket,
        )

    @staticmethod
    def _enqueue_config(
        context: ConnectionContext,
        request: JoinRequest,
        match: Match,
    ) -> None:
        encoder = (
            encode_config_accepted
            if request.requested_config == match.game_config
            else encode_config_overridden
        )
        context.enqueue(encoder(request.request_id, match.game_config))
