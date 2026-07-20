"""Top-level application service: the single public entry point for all
game commands.

Responsibilities:
- Validate and start moves via RuleEngine + RealTimeArbiter.
- Advance simulated time and decide game_over on king capture.
- Expose snapshots for rendering.
- Notify subscribed observers of motion/arrival/game-over events.

Does NOT contain piece-specific movement logic, rendering, input
parsing, or pixel mapping.
"""

import logging

from bus.event_bus import EventBus
from engine.events import Arrival, GameOver, GameStarted, JumpStarted, MotionStarted
from model.board import Board
from model.game_state import GameState
from model.piece import PieceState
from realtime.real_time_arbiter import RealTimeArbiter
from rules.rule_engine import RuleEngine
from rules import piece_rules
from view.renderer import render_snapshot, GameSnapshot, PieceSnapshot

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(self, board: Board):
        """Set up game state, the motion arbiter, and the rule engine for the given board."""
        self._board = board
        self._game_state = GameState()
        self._arbiter = RealTimeArbiter(board)
        self._rule_engine = RuleEngine()
        self._bus = EventBus()

    @property
    def bus(self) -> EventBus:
        """The raw typed-event stream (see engine/events.py) — for subscribers
        that want events as-is rather than adapted to the GameObserver shape."""
        return self._bus

    def subscribe(self, observer):
        """Register a GameObserver and return a function that removes all of its subscriptions."""
        cancellations = [
            self._bus.subscribe(MotionStarted, lambda e: observer.on_motion_started(
                e.piece, e.source, e.destination, e.duration_ms)),
            self._bus.subscribe(JumpStarted, lambda e: observer.on_jump_started(
                e.piece, e.position)),
            self._bus.subscribe(Arrival, lambda e: observer.on_arrival(e.event)),
            self._bus.subscribe(GameOver, lambda e: observer.on_game_over()),
        ]

        def unsubscribe() -> None:
            for cancel in cancellations:
                cancel()

        return unsubscribe

    def start_game(self) -> None:
        """Publish GameStarted — the explicit moment a game begins."""
        self._bus.publish(GameStarted())

    def request_jump(self, source):
        """Start a jump for the piece at source, unless the game is over or the piece is already moving/resting/captured."""
        if self._game_state.game_over:
            logger.info("jump request at %s rejected: game_over", source)
            return
        piece = self._board.get_piece_at(source)
        if piece is None or piece.is_moving() or piece.is_resting() or piece.state == PieceState.CAPTURED:
            logger.info(
                "jump request at %s rejected: %s",
                source,
                "empty_source" if piece is None else piece.state.name,
            )
            return
        self._arbiter.start_jump(piece)
        logger.info("jump started: %s (%s) at %s", piece.id, piece.kind, source)

        self._bus.publish(JumpStarted(piece, source))

    def request_move(self, source, destination):
        """Validate and, if legal, start a move from source to destination; returns a _MoveResult indicating acceptance and reason."""
        if self._game_state.game_over:
            logger.info("move request %s -> %s rejected: game_over", source, destination)
            return _MoveResult(False, "game_over")

        piece = self._board.get_piece_at(source)
        if piece is not None and self._arbiter.has_active_motion(piece):
            logger.info(
                "move request for %s (%s) %s -> %s rejected: motion_in_progress",
                piece.id, piece.kind, source, destination,
            )
            return _MoveResult(False, "motion_in_progress")
        if piece is not None and piece.is_resting():
            logger.info(
                "move request for %s (%s) %s -> %s rejected: resting (%s)",
                piece.id, piece.kind, source, destination, piece.state.name,
            )
            return _MoveResult(False, "resting")

        validation = self._rule_engine.validate_move(self._board, source, destination)
        if not validation.is_valid:
            logger.info("move request %s -> %s rejected: %s", source, destination, validation.reason)
            return _MoveResult(False, validation.reason)

        self._arbiter.start_motion(piece, source, destination)

        duration = piece_rules.get_arrival_duration(piece.kind, source, destination)
        logger.info(
            "move started: %s (%s) %s -> %s, duration=%dms",
            piece.id, piece.kind, source, destination, duration,
        )
        self._bus.publish(MotionStarted(piece, source, destination, duration))

        return _MoveResult(True, "ok")

    def wait(self, milliseconds):
        """Advance simulated time, notify observers of any arrivals, and end the game if a king was captured."""
        arrival_events = self._arbiter.advance_time(milliseconds)

        for event in arrival_events.events:
            logger.info(
                "arrived: %s (%s) %s -> %s, captured=%s",
                event.piece.id, event.piece.kind, event.source, event.destination,
                f"{event.captured_piece.id}({event.captured_piece.kind})" if event.captured_piece else None,
            )
            self._bus.publish(Arrival(event))

        if arrival_events.king_captured:
            logger.info("game over: king captured")
            self._game_state.end_game()
            self._bus.publish(GameOver())

    def snapshot(self, selected_cell=None):
        """Build a read-only GameSnapshot of the current board and game state for rendering."""
        pieces = [
            PieceSnapshot(
                id=p.id,
                kind=p.kind,
                color=str(p.color),
                cell=p.cell,
                state=p.state.name,
            )
            for row in self._board.get_grid()
            for p in row
            if p is not None and p.state != PieceState.CAPTURED
        ]
        return GameSnapshot(
            board_width=self._board.cols,
            board_height=self._board.rows,
            pieces=pieces,
            selected_cell=selected_cell,
            game_over=self._game_state.game_over,
        )

    @property
    def game_over(self):
        """Whether the game has ended."""
        return self._game_state.game_over


class _MoveResult:
    def __init__(self, is_accepted, reason):
        """Store the outcome of a requested move: whether it was accepted and why/why not."""
        self.is_accepted = is_accepted
        self.reason = reason
