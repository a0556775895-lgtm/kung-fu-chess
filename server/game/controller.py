"""Authorize parsed commands and route them to the correct Match engine."""

from model.piece import PieceColor
from networking.protocol import (
    JumpCommand,
    MoveCommand,
    ProtocolError,
    encode_error,
    encode_ok,
    parse_client_command,
)
from server.transport.connection import ConnectionRole


class GameController:
    """Server application boundary for parsing, authorization and engine routing."""

    def __init__(self, registry):
        """Route all commands through the supplied multi-match registry."""
        self._registry = registry

    def handle_message(self, context, message: str) -> str:
        """Parse raw client text and always return a correlated OK or ERR response."""
        try:
            command = parse_client_command(message)
        except ProtocolError as exc:
            return encode_error("0", str(exc))
        return self.handle_command(context, command)

    def handle_command(self, context, command) -> str:
        """Authorize a parsed command and invoke the addressed Match engine."""
        try:
            match = self._registry.get(context.game_id)
        except KeyError:
            return encode_error(command.request_id, "game_not_found")

        rejection = self._authorize(match, context, command)
        if rejection is not None:
            return encode_error(command.request_id, rejection)

        if isinstance(command, MoveCommand):
            result = match.engine.request_move(command.source, command.destination)
        elif isinstance(command, JumpCommand):
            result = match.engine.request_jump(command.source)
        else:  # pragma: no cover - parse_client_command creates known types only
            return encode_error(command.request_id, "unknown_command")

        if not result.is_accepted:
            return encode_error(command.request_id, result.reason)

        match.broadcast_state()
        return encode_ok(command.request_id)

    @staticmethod
    def _authorize(match, context, command) -> str | None:
        """Reject forged role, color, source or piece claims before game-rule checks."""
        if not match.has_connection(context):
            return "connection_not_registered"
        if context.role is not ConnectionRole.PLAYER:
            return "spectator_forbidden"
        if context.color is None:
            return "color_not_assigned"

        expected_wire_color = "W" if context.color is PieceColor.WHITE else "B"
        if command.color != expected_wire_color:
            return "wrong_color"

        snapshot = match.engine.snapshot()
        piece = next((item for item in snapshot.pieces if item.cell == command.source), None)
        if piece is None:
            return "empty_source"
        if piece.color != str(context.color):
            return "wrong_color"
        if piece.kind != command.kind:
            return "piece_mismatch"
        return None
