"""One isolated authoritative game and its assigned connections."""
"""מייצגת משחק בודד"""
from dataclasses import replace
import uuid

from model.piece import PieceColor
from networking.protocols.game import encode_state
from server.game.game_result import FinishReason, GameResult
from server.transport.broadcaster import ServerBroadcaster
from server.transport.connection import ConnectionRole


class Match:
    """Isolate one authoritative engine, sequence stream and connection group."""

    def __init__(
        self,
        game_id: str,
        engine,
        game_config=None,
        *,
        match_instance_id=None,
        completion_service=None,
        activity_logger=None,
    ):
        """Create one game boundary and attach its per-match event broadcaster."""
        if not game_id:
            raise ValueError("INVALID_GAME_ID")
        self.game_id = game_id
        self.match_instance_id = (
            uuid.uuid4().hex
            if match_instance_id is None
            else match_instance_id
        )
        if not isinstance(self.match_instance_id, str) or not self.match_instance_id:
            raise ValueError("INVALID_MATCH_INSTANCE_ID")
        self.engine = engine
        self.game_config = game_config
        self._connections = {}
        self._player_user_ids = {}
        self._player_usernames = {}
        self._sequence = 0
        self._result = None
        self._disconnected_colors = set()
        self._completion_service = completion_service
        self._activity_logger = activity_logger
        self.broadcaster = ServerBroadcaster(
            game_id=game_id,
            bus=engine.bus,
            connections=self.connections,
            next_sequence=self.next_sequence,
            server_time_ms=self.server_time_ms,
            activity_recorder=self.record_activity,
        )

    def add_connection(self, context) -> None:
        """Attach a unique connection that is already assigned to this game id."""
        if context.game_id != self.game_id:
            raise ValueError("CONNECTION_GAME_MISMATCH")
        if context.connection_id in self._connections:
            raise ValueError("CONNECTION_ALREADY_EXISTS")
        if (
            context.role is ConnectionRole.PLAYER
            and context.color is not None
            and context.user_id is not None
        ):
            assigned_user_id = self._player_user_ids.get(context.color)
            if (
                assigned_user_id is not None
                and assigned_user_id != context.user_id
            ):
                raise ValueError("PLAYER_SEAT_ALREADY_ASSIGNED")
            if any(
                connection.role is ConnectionRole.PLAYER
                and connection.color is context.color
                for connection in self._connections.values()
            ):
                raise ValueError("PLAYER_SEAT_ALREADY_CONNECTED")
            self._player_user_ids[context.color] = context.user_id
            if context.username is not None:
                self._player_usernames[context.color] = context.username
        self._connections[context.connection_id] = context
        self.record_activity(
            "connection_joined",
            user_id=context.user_id,
            role=context.role.value,
            color=str(context.color) if context.color is not None else None,
        )

    def remove_connection(self, connection_id: str):
        """Detach a connection, returning it when it was registered."""
        context = self._connections.pop(connection_id, None)
        if context is not None:
            self.record_activity(
                "connection_left",
                user_id=context.user_id,
                role=context.role.value,
            )
        return context

    def has_connection(self, context) -> bool:
        """Check identity, not only id equality, to reject forged contexts."""
        return self._connections.get(context.connection_id) is context

    def connections(self) -> tuple:
        """Return a stable snapshot for synchronous broadcasting."""
        return tuple(self._connections.values())

    def next_sequence(self) -> int:
        """Allocate the next ordering number shared by STATE and EVENT messages."""
        self._sequence += 1
        return self._sequence

    def server_time_ms(self) -> int:
        """Read the single authoritative clock from the engine snapshot."""
        return self.engine.snapshot().server_time_ms

    def record_activity(
        self,
        event_type: str,
        *,
        request_id: str | None = None,
        user_id: int | None = None,
        **details,
    ) -> None:
        """Write one match-scoped activity entry when logging is configured."""
        if self._activity_logger is None:
            return
        self._activity_logger.record(
            event_type,
            server_time_ms=self.server_time_ms(),
            request_id=request_id,
            user_id=user_id,
            **details,
        )

    def snapshot_for(self, context, sequence: int | None = None):
        """Add connection-specific role, color and routing metadata to a snapshot."""
        if not self.has_connection(context):
            raise ValueError("CONNECTION_NOT_REGISTERED")
        base = self.engine.snapshot()
        final_winner = (
            str(self._result.winner_color)
            if self._result is not None
            else base.winner_color
        )
        return replace(
            base,
            game_over=base.game_over or self._result is not None,
            winner_color=final_winner,
            player_names=self._player_names(),
            game_id=self.game_id,
            role=context.role.value,
            assigned_color=str(context.color) if context.color is not None else None,
            sequence=self._sequence if sequence is None else sequence,
        )

    def _player_names(self) -> dict[str, str]:
        """Map persistent player seats to names, even without a live socket."""
        names = {"w": "White", "b": "Black"}
        for color, username in self._player_usernames.items():
            names[str(color)] = username
        return names

    def send_state(self, context) -> None:
        """Queue a fresh full STATE for one registered connection."""
        sequence = self.next_sequence()
        context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def broadcast_state(self) -> None:
        """Queue the same ordered game state for every connection in this Match."""
        sequence = self.next_sequence()
        for context in self.connections():
            context.enqueue(encode_state(self.snapshot_for(context, sequence)))

    def advance_time(self, milliseconds: int) -> None:
        """Advance this Match and convert a king capture into one final result."""
        if milliseconds < 0:
            raise ValueError("NEGATIVE_TICK")
        if self.is_paused:
            return
        self.engine.wait(milliseconds)
        if self.engine.game_over and self._result is None:
            if self.engine.winner_color is None:
                raise RuntimeError("GAME_OVER_WITHOUT_WINNER")
            self.finish(GameResult(
                winner_color=self.engine.winner_color,
                reason=FinishReason.KING_CAPTURE,
                duration_ms=self.server_time_ms(),
            ))

    def pause_for(self, color: PieceColor) -> bool:
        """Pause the whole game while one player seat is disconnected."""
        if not isinstance(color, PieceColor):
            raise ValueError("INVALID_PLAYER_COLOR")
        if self._result is not None:
            return False
        was_paused = self.is_paused
        self._disconnected_colors.add(color)
        return not was_paused

    def resume_for(self, color: PieceColor) -> bool:
        """Resume only after every disconnected player seat has returned."""
        if not isinstance(color, PieceColor):
            raise ValueError("INVALID_PLAYER_COLOR")
        was_paused = self.is_paused
        self._disconnected_colors.discard(color)
        return was_paused and not self.is_paused

    @property
    def is_paused(self) -> bool:
        """Whether at least one player seat is currently disconnected."""
        return bool(self._disconnected_colors)

    @property
    def disconnected_colors(self) -> frozenset[PieceColor]:
        """Expose an immutable view of the seats currently keeping the game paused."""
        return frozenset(self._disconnected_colors)

    def finish(self, result: GameResult) -> bool:
        """Store the first final result and ignore repeated finish attempts."""
        if not isinstance(result, GameResult):
            raise ValueError("INVALID_GAME_RESULT")
        if self._result is not None:
            return False
        if self._completion_service is not None:
            try:
                white_user_id = self._player_user_ids[PieceColor.WHITE]
                black_user_id = self._player_user_ids[PieceColor.BLACK]
            except KeyError as exc:
                raise RuntimeError("AUTHENTICATED_PLAYERS_REQUIRED") from exc
            self._completion_service.complete(
                match_instance_id=self.match_instance_id,
                white_user_id=white_user_id,
                black_user_id=black_user_id,
                result=result,
            )
        self._result = result
        self.record_activity(
            "game_finished",
            winner_color=str(result.winner_color),
            reason=result.reason.value,
            duration_ms=result.duration_ms,
        )
        self.broadcast_state()
        self.broadcaster.publish_game_over()
        if self._activity_logger is not None:
            self._activity_logger.close()
        return True

    @property
    def result(self) -> GameResult | None:
        """Return the immutable final result, or None while the game is active."""
        return self._result

    @property
    def player_user_ids(self) -> dict[PieceColor, int]:
        """Return persistent seat identities independently of live connections."""
        return dict(self._player_user_ids)

    @property
    def player_usernames(self) -> dict[PieceColor, str]:
        """Return persistent display names independently of live connections."""
        return dict(self._player_usernames)

    def close(self) -> None:
        """Unsubscribe the broadcaster and release all connection references."""
        self.record_activity("match_closed")
        self.broadcaster.close()
        if self._activity_logger is not None:
            self._activity_logger.close()
        self._connections.clear()
        self._player_user_ids.clear()
        self._player_usernames.clear()
        self._disconnected_colors.clear()
