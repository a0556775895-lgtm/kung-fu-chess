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

from model.board import Board
from model.game_state import GameState
from model.piece import PieceState
from realtime.real_time_arbiter import RealTimeArbiter
from rules.rule_engine import RuleEngine
from rules import piece_rules
from view.renderer import render_snapshot, GameSnapshot, PieceSnapshot


class GameEngine:
    def __init__(self, board: Board):
        """Set up game state, the motion arbiter, and the rule engine for the given board."""
        self._board = board
        self._game_state = GameState()
        self._arbiter = RealTimeArbiter(board)
        self._rule_engine = RuleEngine()
        self._observers = []

    def subscribe(self, observer) -> None:
        """רושם GameObserver לקבלת התראות on_arrival/on_motion_started/
        on_jump_started/on_game_over. ראו view/observer.py."""
        self._observers.append(observer)

    def request_jump(self, source):
        """Start a jump for the piece at source, unless the game is over or the piece is already moving/resting/captured."""
        if self._game_state.game_over:
            return
        piece = self._board.get_piece_at(source)
        if piece is None or piece.is_moving() or piece.is_resting() or piece.state == PieceState.CAPTURED:
            return
        self._arbiter.start_jump(piece)

        for observer in self._observers:
            observer.on_jump_started(piece, source)

    def request_move(self, source, destination):
        """Validate and, if legal, start a move from source to destination; returns a _MoveResult indicating acceptance and reason."""
        if self._game_state.game_over:
            return _MoveResult(False, "game_over")

        piece = self._board.get_piece_at(source)
        if piece is not None and self._arbiter.has_active_motion(piece):
            return _MoveResult(False, "motion_in_progress")
        if piece is not None and piece.is_resting():
            return _MoveResult(False, "resting")

        validation = self._rule_engine.validate_move(self._board, source, destination)
        if not validation.is_valid:
            return _MoveResult(False, validation.reason)

        self._arbiter.start_motion(piece, source, destination)

        duration = piece_rules.get_arrival_duration(piece.kind, source, destination)
        for observer in self._observers:
            observer.on_motion_started(piece, source, destination, duration)

        return _MoveResult(True, "ok")

    def wait(self, milliseconds):
        """Advance simulated time, notify observers of any arrivals, and end the game if a king was captured."""
        arrival_events = self._arbiter.advance_time(milliseconds)

        for event in arrival_events.events:
            for observer in self._observers:
                observer.on_arrival(event)

        if arrival_events.king_captured:
            self._game_state.end_game()
            for observer in self._observers:
                observer.on_game_over()

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